"""Click CLI — 'review' (full PR review flow) and 'update-registry' commands."""

import json
import logging
import os
import sys

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """PR Reviewer — AI-powered PR review tool for channelkart-flutter."""
    pass


@cli.command()
@click.option("--pr-number", type=int, envvar="PR_NUMBER", required=True, help="PR number to review")
@click.option("--repo", envvar="GITHUB_REPO", required=True, help="GitHub repo (owner/repo)")
@click.option("--branch", envvar="BRANCH_NAME", default="", help="Branch name")
@click.option("--base-sha", envvar="BASE_SHA", default="", help="Base commit SHA")
@click.option("--head-sha", envvar="HEAD_SHA", default="", help="Head commit SHA")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
def review(pr_number: int, repo: str, branch: str, base_sha: str, head_sha: str, registry_path: str):
    """Run a full AI review on a GitHub PR."""
    from reviewer import config
    config.validate_required()
    from reviewer.ai_reviewer import extract_merge_recommendation, format_github_comment, run_review
    from reviewer.figma_client import extract_design_specs, get_file_node
    from reviewer.git_analyzer import ChangedFile, extract_commit_log, parse_unified_diff
    from reviewer.github_client import delete_old_review_comments, get_pr, get_pr_diff, post_pr_comment
    from reviewer.jira_client import extract_jira_key, get_issue_context, get_open_bugs
    from reviewer.lob_mapper import get_sentinel_warnings, map_paths_to_features
    from reviewer.prompt_builder import build_prompt
    from reviewer.registry import get_feature_context

    # Override registry path
    config.REGISTRY_PATH = registry_path

    click.echo(f"🔍 Reviewing PR #{pr_number} on {repo}...")

    # 1. Fetch PR data
    try:
        pr_data = get_pr(pr_number, repo)
    except Exception as e:
        click.echo(f"❌ Failed to fetch PR: {e}", err=True)
        sys.exit(1)

    pr_body = pr_data.get("body") or ""
    if not branch:
        branch = pr_data.get("head", {}).get("ref", "")

    click.echo(f"  Branch: {branch}")

    # 2. Fetch diff and parse
    diff_text = get_pr_diff(pr_number, repo)
    changed_files = parse_unified_diff(diff_text)
    click.echo(f"  Files changed: {len(changed_files)}")

    # 3. Extract Jira context
    jira_key = extract_jira_key(branch) or extract_jira_key(pr_data.get("title", ""))
    jira_context: dict = {}
    if jira_key:
        click.echo(f"  Jira ticket: {jira_key}")
        jira_context = get_issue_context(jira_key)
        # Also search for open bugs
        project_key = jira_key.split("-")[0]
        file_paths = [f.path for f in changed_files]
        features = map_paths_to_features(file_paths)
        for feat_name in features:
            if feat_name.startswith("_"):
                continue
            bugs = get_open_bugs(project_key, feat_name)
            if bugs:
                jira_context.setdefault("open_bugs", []).extend(bugs)
    else:
        click.echo("  No Jira ticket detected")

    # 4. Figma specs
    figma_specs = None
    figma_urls = jira_context.get("figma_urls", [])
    # Also check PR body for Figma URLs
    from reviewer.jira_client import extract_figma_urls
    figma_urls.extend(extract_figma_urls(pr_body))

    if figma_urls:
        click.echo(f"  Figma links found: {len(figma_urls)}")
        for fu in figma_urls[:3]:  # Cap at 3
            node = get_file_node(fu["file_key"], fu.get("node_id", ""))
            if node:
                figma_specs = extract_design_specs(node)
                break  # Use first successful one
    else:
        click.echo("  No Figma links found")

    # 5. Registry context
    file_paths = [f.path for f in changed_files]
    feature_map = map_paths_to_features(file_paths)
    feature_contexts = {}
    for feat_name in feature_map:
        if not feat_name.startswith("_"):
            feature_contexts[feat_name] = get_feature_context(feat_name)

    click.echo(f"  Features detected: {list(feature_contexts.keys()) or ['none']}")

    # 6. Sentinel warnings
    sentinel_warnings = get_sentinel_warnings(file_paths)
    if sentinel_warnings:
        for w in sentinel_warnings:
            click.echo(f"  {w}")

    # 7. Commits
    commits: list[dict] = []
    # If we have git access, we could extract commits; for now rely on PR data
    pr_commits = pr_data.get("commits", 0)
    click.echo(f"  Commits: {pr_commits}")

    # 8. Build prompt
    system_prompt, user_prompt = build_prompt(
        jira_context=jira_context,
        figma_specs=figma_specs,
        feature_contexts=feature_contexts,
        branch_name=branch,
        commits=commits,
        changed_files=changed_files,
        pr_body=pr_body,
    )

    prompt_tokens = len(user_prompt) // 4
    click.echo(f"  Prompt size: ~{prompt_tokens:,} tokens")

    # 9. Call Claude
    click.echo("  🧠 Running AI review...")
    review_text = run_review(system_prompt, user_prompt)

    # 10. Format and post comment
    comment_body = format_github_comment(review_text, sentinel_warnings)

    # Delete old review comments first
    deleted = delete_old_review_comments(pr_number, repo_slug=repo)
    if deleted:
        click.echo(f"  Deleted {deleted} old review comment(s)")

    post_pr_comment(pr_number, comment_body, repo_slug=repo)

    # Extract recommendation
    from reviewer.ai_reviewer import parse_review_sections
    sections = parse_review_sections(review_text)
    recommendation = extract_merge_recommendation(sections)
    click.echo(f"\n✅ Review posted — Recommendation: {recommendation}")


@cli.command("update-registry")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
@click.option("--flutter-repo-path", required=True, help="Path to Flutter repo")
@click.option("--changed-files", required=True, help="Comma-separated list of changed files")
@click.option("--jira-key", default="", help="Jira ticket key from merge commit")
@click.option("--commit-sha", default="", help="Merge commit SHA")
def update_registry(
    registry_path: str,
    flutter_repo_path: str,
    changed_files: str,
    jira_key: str,
    commit_sha: str,
):
    """Update the feature registry after a merge to master."""
    from reviewer import config
    from reviewer.jira_client import extract_jira_key, get_issue_context
    from reviewer.lob_mapper import map_paths_to_features
    from reviewer.registry import add_jira_history, update_git_history

    config.REGISTRY_PATH = registry_path

    file_list = [f.strip() for f in changed_files.split(",") if f.strip()]
    click.echo(f"📝 Updating registry for {len(file_list)} changed files...")

    # Map files to features
    feature_map = map_paths_to_features(file_list)

    for feat_name, feat_files in feature_map.items():
        if feat_name.startswith("_"):
            click.echo(f"  Skipping {feat_name} ({len(feat_files)} files)")
            continue

        click.echo(f"  Updating feature: {feat_name} ({len(feat_files)} files)")

        # Update git history
        for fpath in feat_files:
            update_git_history(feat_name, fpath, commit_sha, "ci-bot")

        # Add Jira history if we have a ticket
        if jira_key:
            ctx = get_issue_context(jira_key)
            if ctx.get("summary"):
                add_jira_history(feat_name, {
                    "ticket_key": jira_key,
                    "summary": ctx["summary"],
                    "ticket_type": ctx.get("type", ""),
                    "epic": ctx.get("epic", ""),
                    "status": ctx.get("status", ""),
                    "lobs_affected": [],
                    "figma_links": [u["url"] for u in ctx.get("figma_urls", [])],
                    "acceptance_criteria": ctx.get("acceptance_criteria", []),
                    "commits": [{"sha": commit_sha, "message": "", "date": "", "files_changed": feat_files}],
                    "branch": "",
                })

    click.echo("✅ Registry update complete")


@cli.command("query")
@click.argument("question")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
@click.option("--no-live", is_flag=True, default=False, help="Skip live Jira/GitHub API calls")
def query(question: str, registry_path: str, no_live: bool):
    """Ask a natural language question about the feature registry or Jira history."""
    from reviewer import config
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        click.echo("ERROR: ANTHROPIC_API_KEY is not set", err=True)
        sys.exit(1)
    config.REGISTRY_PATH = registry_path

    from reviewer.kb_query import ask
    try:
        answer = ask(question, registry_path=registry_path, use_live=not no_live)
        click.echo(answer)
    except Exception as e:
        click.echo(f"❌ Query failed: {e}", err=True)
        sys.exit(1)


@cli.command("shell")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
@click.option("--no-live", is_flag=True, default=False, help="Skip live Jira/GitHub API calls")
def shell(registry_path: str, no_live: bool):
    """Start an interactive knowledge base REPL. Type 'exit' or 'quit' to leave."""
    from reviewer import config
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        click.echo("ERROR: ANTHROPIC_API_KEY is not set", err=True)
        sys.exit(1)
    config.REGISTRY_PATH = registry_path

    from reviewer.kb_query import ask

    click.echo("Knowledge Base Shell — channelkart-flutter registry + Jira")
    click.echo("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            question = click.prompt("kb", prompt_suffix="> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye.")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            click.echo("Bye.")
            break

        try:
            answer = ask(question, registry_path=registry_path, use_live=not no_live)
            click.echo(f"\n{answer}\n")
        except Exception as e:
            click.echo(f"❌ Error: {e}\n", err=True)


@cli.command("migrate-db")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
def migrate_db(registry_path: str):
    """Migrate JSON registry files into the SQLite database."""
    from reviewer import config
    config.REGISTRY_PATH = registry_path

    from reviewer.database import migrate_from_json
    click.echo(f"Migrating JSON registry → SQLite ({registry_path})...")
    stats = migrate_from_json(registry_path)
    click.echo(f"  Features:     {stats['features']}")
    click.echo(f"  LOBs:         {stats['lobs']}")
    click.echo(f"  Overrides:    {stats['overrides']}")
    click.echo(f"  Jira tickets: {stats['jira_tickets']}")
    click.echo(f"  Git files:    {stats['git_files']}")
    click.echo("Done.")


@cli.command("serve")
@click.option("--registry-path", envvar="REGISTRY_PATH", default="registry", help="Path to registry dir")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to listen on")
def serve(registry_path: str, host: str, port: int):
    """Start the dashboard API server."""
    from reviewer import config
    config.REGISTRY_PATH = registry_path

    from reviewer.database import init_db
    init_db()

    import uvicorn
    click.echo(f"Starting API server on {host}:{port}...")
    click.echo(f"  Registry: {registry_path}")
    click.echo(f"  Dashboard: http://localhost:3000")
    uvicorn.run("reviewer.api:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    cli()
