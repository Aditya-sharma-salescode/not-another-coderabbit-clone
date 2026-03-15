"""
AI-powered PR review orchestration using Claude.

Flow:
  1. Build a detailed review prompt (diff + Jira context + PR metadata)
  2. Call Claude with adaptive thinking + structured output
  3. Return a validated PRReview object
"""

import logging

import anthropic

from config import settings
from models import PRReview
from services.diff_parser import format_diff_for_review

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """\
You are a senior software engineer performing a thorough automated code review.

Your responsibilities:
1. Identify bugs, logic errors, and potential runtime failures
2. Flag security vulnerabilities (injection attacks, broken auth, sensitive data exposure, \
insecure dependencies, etc.)
3. Spot performance issues (N+1 queries, blocking calls, memory leaks, inefficient algorithms)
4. Assess code quality (readability, maintainability, SOLID principles, DRY violations)
5. Check whether the implementation actually satisfies the Jira ticket requirements
6. Identify missing or inadequate tests

Rating scale:
  9–10 → Excellent, approve immediately
  7–8  → Good with minor suggestions
  5–6  → Notable issues, changes recommended
  3–4  → Significant problems, must fix
  1–2  → Severe issues, do not merge

For inline_comments: ONLY reference line numbers explicitly shown in the diff \
(marked with [+LINE] for new lines or [ LINE] for context lines). Never reference a \
line number that isn't in the diff. Keep comments concise and actionable.\
"""


def _build_prompt(
    pr_title: str,
    pr_body: str,
    base_branch: str,
    head_branch: str,
    jira_context: str,
    diff_text: str,
) -> str:
    sections: list[str] = []

    sections.append(f"## Pull Request\n**Title:** {pr_title}\n**Branch:** `{head_branch}` → `{base_branch}`")

    if pr_body and pr_body.strip():
        sections.append(f"**Description:**\n{pr_body.strip()}")

    if jira_context:
        sections.append(f"## Jira Ticket Context\n{jira_context}")
    else:
        sections.append("## Jira Ticket Context\nNo Jira ticket found for this PR.")

    sections.append(
        "## Code Changes\n"
        "Each changed line is prefixed with its line number:\n"
        "  [+LINE] = added line (RIGHT side, use this number for inline comments)\n"
        "  [ LINE] = context line (unchanged but visible in diff)\n"
        "  [ DEL]  = deleted line (no line number, cannot be commented on)\n\n"
        + diff_text
    )

    return "\n\n".join(sections)


async def run_review(
    pr_title: str,
    pr_body: str,
    base_branch: str,
    head_branch: str,
    pr_files: list[dict],
    jira_context: str,
) -> PRReview:
    """
    Run the full AI code review and return a structured PRReview.
    Uses Claude Opus 4.6 with adaptive thinking for deep reasoning.
    """
    diff_text = format_diff_for_review(pr_files)
    prompt = _build_prompt(pr_title, pr_body, base_branch, head_branch, jira_context, diff_text)

    logger.info("Sending PR to Claude for review (prompt ~%d chars)", len(prompt))

    response = await _client.messages.parse(
        model="claude-opus-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_format=PRReview,
    )

    review: PRReview = response.parsed_output
    logger.info(
        "Review complete — rating: %d/10, inline comments: %d, blocking: %d",
        review.rating,
        len(review.inline_comments),
        len(review.blocking_issues),
    )
    return review
