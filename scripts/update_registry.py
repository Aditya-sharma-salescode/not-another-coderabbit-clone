#!/usr/bin/env python3
"""
Incremental registry update — called by GitHub Actions after each merge to master.

Usage:
    python scripts/update_registry.py \
        --registry-path registry \
        --flutter-repo-path /path/to/flutter-repo \
        --changed-files "lib/features/cart/widgets/cart_item.dart,lib/features/cart/model/cart.dart" \
        --jira-key COCA-850 \
        --commit-sha 60abf436
"""

import json
import os
import subprocess
import sys

import click

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option("--registry-path", required=True, help="Path to registry directory")
@click.option("--flutter-repo-path", required=True, help="Path to Flutter repo")
@click.option("--changed-files", required=True, help="Comma-separated changed file paths")
@click.option("--jira-key", default="", help="Jira ticket key from merge commit")
@click.option("--commit-sha", default="", help="Merge commit SHA")
def update(registry_path: str, flutter_repo_path: str, changed_files: str, jira_key: str, commit_sha: str):
    """Incremental registry update after merge."""
    from reviewer import config
    from reviewer.lob_mapper import map_paths_to_features
    from reviewer.registry import add_jira_history, load_feature, update_feature, update_git_history

    config.REGISTRY_PATH = registry_path

    file_list = [f.strip() for f in changed_files.split(",") if f.strip()]
    if not file_list:
        click.echo("No changed files provided, nothing to update.")
        return

    click.echo(f"📝 Updating registry for {len(file_list)} changed files...")

    # Map files to features
    feature_map = map_paths_to_features(file_list)

    # Get commit author
    author = "unknown"
    if commit_sha and os.path.isdir(flutter_repo_path):
        try:
            result = subprocess.run(
                ["git", "log", "--format=%ae", "-n", "1", commit_sha],
                cwd=flutter_repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                author = result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

    for feat_name, feat_files in feature_map.items():
        if feat_name.startswith("_"):
            click.echo(f"  Skipping sentinel: {feat_name} ({len(feat_files)} files)")
            continue

        click.echo(f"  Updating: {feat_name} ({len(feat_files)} files)")

        # Update git file history
        for fpath in feat_files:
            update_git_history(feat_name, fpath, commit_sha, author)

        # Add Jira history
        if jira_key:
            try:
                from reviewer.jira_client import get_issue_context
                ctx = get_issue_context(jira_key)
                if ctx.get("summary"):
                    # Get commit message
                    commit_msg = ""
                    if commit_sha and os.path.isdir(flutter_repo_path):
                        try:
                            result = subprocess.run(
                                ["git", "log", "--format=%s", "-n", "1", commit_sha],
                                cwd=flutter_repo_path,
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            if result.returncode == 0:
                                commit_msg = result.stdout.strip()
                        except (subprocess.TimeoutExpired, OSError):
                            pass

                    # Get commit date
                    commit_date = ""
                    if commit_sha and os.path.isdir(flutter_repo_path):
                        try:
                            result = subprocess.run(
                                ["git", "log", "--format=%ad", "--date=short", "-n", "1", commit_sha],
                                cwd=flutter_repo_path,
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            if result.returncode == 0:
                                commit_date = result.stdout.strip()
                        except (subprocess.TimeoutExpired, OSError):
                            pass

                    add_jira_history(feat_name, {
                        "ticket_key": jira_key,
                        "summary": ctx["summary"],
                        "ticket_type": ctx.get("type", ""),
                        "epic": ctx.get("epic", ""),
                        "status": ctx.get("status", ""),
                        "lobs_affected": [],
                        "figma_links": [u["url"] for u in ctx.get("figma_urls", [])],
                        "acceptance_criteria": ctx.get("acceptance_criteria", []),
                        "commits": [{
                            "sha": commit_sha,
                            "message": commit_msg,
                            "date": commit_date,
                            "files_changed": feat_files,
                        }],
                        "branch": "",
                    })
            except Exception as e:
                click.echo(f"  ⚠️ Jira fetch failed for {jira_key}: {e}")

    click.echo("✅ Registry update complete")


if __name__ == "__main__":
    update()
