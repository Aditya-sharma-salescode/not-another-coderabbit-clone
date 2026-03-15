"""
Automated PR Reviewer — FastAPI webhook server.

GitHub sends a webhook POST to /webhook whenever a pull request is opened,
updated, or reopened. This server:
  1. Verifies the HMAC-SHA256 signature
  2. Dispatches the review as a background task (returns 202 immediately)
  3. Fetches PR files + Jira ticket context
  4. Calls Claude for a structured AI review
  5. Posts inline comments + summary back to GitHub
  6. Sets a commit status check (pass/fail) as the CI gate

Setup:
  1. Copy .env.example to .env and fill in your secrets
  2. pip install -r requirements.txt
  3. uvicorn main:app --host 0.0.0.0 --port 8000
  4. Point your GitHub webhook at http://your-server:8000/webhook
     (use ngrok for local testing: ngrok http 8000)
  5. Optionally enable branch protection requiring "automated-pr-reviewer/review"
"""

import hashlib
import hmac
import logging

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from config import settings
from models import PRReview
from services import github, jira
from services.diff_parser import build_line_maps, is_line_valid
from services.reviewer import run_review

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Automated PR Reviewer")


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@app.post("/webhook", status_code=202)
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    body = await request.body()

    # 1. Verify HMAC signature
    _verify_signature(body, x_hub_signature_256)

    # 2. Only handle pull_request events
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = await request.json()
    action = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"action={action}"}

    pr = payload["pull_request"]
    repo_data = payload["repository"]

    context = {
        "owner": repo_data["owner"]["login"],
        "repo": repo_data["name"],
        "pull_number": pr["number"],
        "head_sha": pr["head"]["sha"],
        "head_branch": pr["head"]["ref"],
        "base_branch": pr["base"]["ref"],
        "pr_title": pr["title"],
        "pr_body": pr.get("body") or "",
    }

    logger.info(
        "Queuing review for %s/%s PR #%d (%s)",
        context["owner"],
        context["repo"],
        context["pull_number"],
        action,
    )

    # 3. Kick off review in background so GitHub doesn't time out
    background_tasks.add_task(process_review, context)

    return {"status": "accepted"}


# ---------------------------------------------------------------------------
# Background review pipeline
# ---------------------------------------------------------------------------


async def process_review(ctx: dict) -> None:
    owner = ctx["owner"]
    repo = ctx["repo"]
    pull_number = ctx["pull_number"]
    head_sha = ctx["head_sha"]

    try:
        # Mark PR as "pending" immediately so the team sees it's in progress
        await github.set_commit_status(
            owner, repo, head_sha,
            state="pending",
            description="AI review in progress…",
        )

        # Fetch PR files and Jira context in parallel
        pr_files, pr_detail = await _fetch_pr_data(owner, repo, pull_number)
        jira_context = await _fetch_jira_context(
            ctx["head_branch"], ctx["pr_title"], ctx["pr_body"]
        )

        # Run Claude review
        review: PRReview = await run_review(
            pr_title=ctx["pr_title"],
            pr_body=ctx["pr_body"],
            base_branch=ctx["base_branch"],
            head_branch=ctx["head_branch"],
            pr_files=pr_files,
            jira_context=jira_context,
        )

        # Build inline comment payloads, validating each line against the diff
        line_maps = build_line_maps(pr_files)
        valid_comments, skipped = _build_github_comments(review, line_maps)

        # Compose the overall review body
        review_body = _format_review_body(review, skipped)

        # Determine GitHub review event
        if review.rating >= 9:
            event = "APPROVE"
        elif review.blocking_issues:
            event = "REQUEST_CHANGES"
        else:
            event = "COMMENT"

        # Post the review
        await github.post_review(
            owner, repo, pull_number,
            commit_id=head_sha,
            body=review_body,
            comments=valid_comments,
            event=event,
        )

        # Set final commit status
        passed = review.rating >= settings.review_pass_threshold
        await github.set_commit_status(
            owner, repo, head_sha,
            state="success" if passed else "failure",
            description=_status_description(review, passed),
        )

        logger.info(
            "PR #%d review posted — rating %d/10, %s",
            pull_number,
            review.rating,
            "PASSED" if passed else "FAILED",
        )

    except Exception:
        logger.exception("Review pipeline failed for PR #%d", pull_number)
        # Always resolve the pending status so the PR isn't stuck
        try:
            await github.set_commit_status(
                owner, repo, head_sha,
                state="error",
                description="AI review failed — check server logs",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_pr_data(owner: str, repo: str, pull_number: int):
    """Fetch PR files and detail (could be parallelised with asyncio.gather)."""
    import asyncio
    return await asyncio.gather(
        github.get_pr_files(owner, repo, pull_number),
        github.get_pr_detail(owner, repo, pull_number),
    )


async def _fetch_jira_context(branch: str, title: str, body: str) -> str:
    """Extract Jira ticket ID from branch / title / body and fetch context."""
    ticket_id = (
        jira.extract_ticket_id(branch)
        or jira.extract_ticket_id(title)
        or jira.extract_ticket_id(body)
    )
    if not ticket_id:
        logger.info("No Jira ticket ID found in branch=%s or PR text", branch)
        return ""
    logger.info("Found Jira ticket: %s", ticket_id)
    return await jira.get_ticket_context(ticket_id)


def _build_github_comments(
    review: PRReview, line_maps: dict
) -> tuple[list[dict], list[dict]]:
    """
    Convert PRReview.inline_comments into GitHub API payloads.
    Returns (valid_comments, skipped_comments).
    """
    valid: list[dict] = []
    skipped: list[dict] = []

    for ic in review.inline_comments:
        if is_line_valid(line_maps, ic.path, ic.line):
            severity_icon = {"critical": "🚨", "warning": "⚠️", "suggestion": "💡"}.get(
                ic.severity, "📝"
            )
            valid.append({
                "path": ic.path,
                "line": ic.line,
                "side": "RIGHT",
                "body": f"{severity_icon} **[{ic.severity.upper()}]** {ic.body}",
            })
        else:
            skipped.append({"path": ic.path, "line": ic.line, "body": ic.body, "severity": ic.severity})

    return valid, skipped


def _format_review_body(review: PRReview, skipped: list[dict]) -> str:
    """Build the markdown summary posted as the top-level review comment."""
    rating_bar = "🟩" * review.rating + "⬜" * (10 - review.rating)
    lines = [
        f"## 🤖 Automated PR Review\n",
        f"**Rating:** {review.rating}/10  {rating_bar}\n",
        f"### Summary\n{review.summary}\n",
    ]

    if review.jira_alignment and review.jira_alignment != "No Jira ticket provided":
        lines.append(f"### Jira Alignment\n{review.jira_alignment}\n")

    if review.blocking_issues:
        lines.append("### 🚨 Blocking Issues (must fix before merge)")
        lines.extend(f"- {issue}" for issue in review.blocking_issues)
        lines.append("")

    if review.security_concerns:
        lines.append("### 🔒 Security Concerns")
        lines.extend(f"- {concern}" for concern in review.security_concerns)
        lines.append("")

    if review.recommendations:
        lines.append("### 💡 Recommendations")
        lines.extend(f"- {rec}" for rec in review.recommendations)
        lines.append("")

    # Inline comments that couldn't be posted (line wasn't in diff)
    if skipped:
        lines.append("### 📎 Additional Comments (lines outside diff window)")
        for s in skipped:
            icon = {"critical": "🚨", "warning": "⚠️", "suggestion": "💡"}.get(s["severity"], "📝")
            lines.append(f"- **{s['path']}:{s['line']}** {icon} {s['body']}")
        lines.append("")

    lines.append(
        f"\n---\n*Reviewed by [automated-pr-reviewer](https://github.com) "
        f"using Claude Opus · Threshold: {settings.review_pass_threshold}/10*"
    )

    return "\n".join(lines)


def _status_description(review: PRReview, passed: bool) -> str:
    status = "✅ Passed" if passed else "❌ Failed"
    issues = len(review.blocking_issues)
    issue_text = f" · {issues} blocking issue{'s' if issues != 1 else ''}" if issues else ""
    return f"AI Review: {review.rating}/10 — {status}{issue_text}"


def _verify_signature(body: bytes, signature_header: str) -> None:
    if not signature_header:
        raise HTTPException(status_code=403, detail="Missing X-Hub-Signature-256 header")

    expected = "sha256=" + hmac.new(
        key=settings.github_webhook_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "jira_enabled": settings.jira_enabled,
        "pass_threshold": settings.review_pass_threshold,
    }
