#!/usr/bin/env python3
"""
One-time seed script that walks a Flutter repo to build the initial registry.

Usage:
    python scripts/bootstrap_registry.py --flutter-repo-path /path/to/channelkart-flutter

Walks:
    - lib/features/ for feature paths
    - lib/sfa/features/ for SFA feature paths
    - lib/channelKart/features/ for ChannelKart feature paths
    - integration_test/ for LOB folders and page overrides
    - integration_test/config/*.json for per-LOB config
    - git log for commit history
    - Jira API for ticket details (if configured)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import click

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option("--flutter-repo-path", required=True, help="Path to channelkart-flutter repo")
@click.option("--registry-path", default="registry", help="Output registry directory")
@click.option("--skip-jira", is_flag=True, help="Skip Jira API calls")
@click.option("--skip-git", is_flag=True, help="Skip git history analysis")
def bootstrap(flutter_repo_path: str, registry_path: str, skip_jira: bool, skip_git: bool):
    """Bootstrap the feature registry from a Flutter repo."""

    if not os.path.isdir(flutter_repo_path):
        click.echo(f"❌ Flutter repo not found at: {flutter_repo_path}", err=True)
        sys.exit(1)

    click.echo(f"🔧 Bootstrapping registry from: {flutter_repo_path}")
    click.echo(f"   Output: {registry_path}")

    os.makedirs(os.path.join(registry_path, "features"), exist_ok=True)

    # --- Step 1: Discover features ---
    click.echo("\n📁 Discovering features...")
    features = _discover_features(flutter_repo_path)
    click.echo(f"   Found {len(features)} features")

    # --- Step 2: Build path_to_feature mapping ---
    path_to_feature = {}
    for feat in features:
        for src_path in feat["source_paths"]:
            path_to_feature[src_path] = feat["feature_name"]

    # Add sentinel paths
    sentinel_paths = {
        "_lob_config": "CRITICAL: affects ALL LOBs at runtime",
        "_routing": "CRITICAL: affects ALL navigation flows",
        "_app_root": "CRITICAL: app entry point",
    }
    path_to_feature["lib/constants/config_lob.dart"] = "_lob_config"
    path_to_feature["lib/go_router.dart"] = "_routing"
    path_to_feature["lib/main.dart"] = "_app_root"

    # --- Step 3: Discover LOBs ---
    click.echo("\n📁 Discovering LOBs...")
    lob_data = _discover_lobs(flutter_repo_path)
    click.echo(f"   Found {len(lob_data)} LOBs")

    # --- Step 4: Git history per feature ---
    git_histories: dict[str, dict] = {}
    if not skip_git:
        click.echo("\n📜 Analyzing git history...")
        git_histories = _analyze_git_history(flutter_repo_path, features)
        click.echo(f"   Analyzed history for {len(git_histories)} features")

    # --- Step 5: Jira history (optional) ---
    jira_histories: dict[str, list] = {}
    if not skip_jira:
        try:
            from reviewer.jira_client import get_issue_context, extract_jira_key
            click.echo("\n🎫 Fetching Jira history...")
            jira_histories = _fetch_jira_history(flutter_repo_path, features)
            click.echo(f"   Fetched Jira data for {len(jira_histories)} features")
        except Exception as e:
            click.echo(f"   ⚠️ Jira fetch failed: {e}")

    # --- Step 6: Write index.json ---
    index = {
        "version": "1.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "path_to_feature": dict(sorted(path_to_feature.items())),
        "sentinel_paths": sentinel_paths,
        "jira_projects": ["CSLC", "COCA", "CT", "MYB2B", "PS", "UI"],
    }
    index_path = os.path.join(registry_path, "index.json")
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    click.echo(f"\n✅ Written: {index_path} ({len(path_to_feature)} paths)")

    # --- Step 7: Write lob_index.json ---
    lob_index = {
        "version": "1.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "lobs": lob_data,
    }
    lob_path = os.path.join(registry_path, "lob_index.json")
    with open(lob_path, "w") as f:
        json.dump(lob_index, f, indent=2)
    click.echo(f"✅ Written: {lob_path} ({len(lob_data)} LOBs)")

    # --- Step 8: Write per-feature JSONs ---
    click.echo(f"\n📝 Writing feature files...")
    for feat in features:
        fname = feat["feature_name"]
        feat_data = {
            "feature_name": fname,
            "source_paths": feat["source_paths"],
            "sub_paths": feat.get("sub_paths", {}),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "lob_context": _get_lob_context(fname, lob_data),
            "jira_history": jira_histories.get(fname, []),
            "git_file_history": git_histories.get(fname, {}),
            "related_features": feat.get("related_features", []),
        }
        feat_path = os.path.join(registry_path, "features", f"{fname}.json")
        with open(feat_path, "w") as f:
            json.dump(feat_data, f, indent=2)

    click.echo(f"✅ Written {len(features)} feature files")
    click.echo(f"\n🎉 Bootstrap complete!")


def _discover_features(repo_path: str) -> list[dict]:
    """Walk lib/features/, lib/sfa/features/, lib/channelKart/features/ for feature dirs."""
    features = []
    namespaces = [
        ("lib/features/", ""),
        ("lib/sfa/features/", "sfa_"),
        ("lib/channelKart/features/", "ck_"),
    ]

    for ns_path, prefix in namespaces:
        full_path = os.path.join(repo_path, ns_path)
        if not os.path.isdir(full_path):
            continue

        for entry in sorted(os.listdir(full_path)):
            entry_path = os.path.join(full_path, entry)
            if not os.path.isdir(entry_path):
                continue

            feature_name = f"{prefix}{entry}"
            source_path = f"{ns_path}{entry}/"

            # Discover sub-paths
            sub_paths = {}
            for sub in ("model", "models", "screens", "services", "provider", "providers", "widgets"):
                sub_full = os.path.join(entry_path, sub)
                if os.path.isdir(sub_full):
                    sub_paths[sub] = f"{source_path}{sub}/"

            features.append({
                "feature_name": feature_name,
                "source_paths": [source_path],
                "sub_paths": sub_paths,
            })

    return features


def _discover_lobs(repo_path: str) -> dict:
    """Walk integration_test/ for LOB folders and page overrides."""
    lob_data = {}
    it_path = os.path.join(repo_path, "integration_test")
    if not os.path.isdir(it_path):
        return lob_data

    # Known LOB folders
    for entry in sorted(os.listdir(it_path)):
        entry_path = os.path.join(it_path, entry)
        if not os.path.isdir(entry_path) or entry in ("config", "common", "utils", "helpers"):
            continue

        lob = {
            "name": entry,
            "override_pages": [],
            "config_keys": [],
            "overrides": {},
        }

        # Find .dart override pages
        for f in os.listdir(entry_path):
            if f.endswith(".dart"):
                lob["override_pages"].append(f)

        lob_data[entry] = lob

    # Parse config files for LOB → feature mappings
    config_dir = os.path.join(it_path, "config")
    if os.path.isdir(config_dir):
        for config_file in os.listdir(config_dir):
            if not config_file.endswith(".json"):
                continue
            config_name = config_file.removesuffix(".json")
            try:
                with open(os.path.join(config_dir, config_file)) as f:
                    config_data = json.load(f)
                for lob_key in config_data:
                    # Try to match LOB key to known LOBs
                    for known_lob in lob_data:
                        if known_lob.lower() in lob_key.lower() or lob_key.lower() in known_lob.lower():
                            lob_data[known_lob]["config_keys"].append(config_name)
                            break
            except (json.JSONDecodeError, OSError):
                pass

    return lob_data


def _get_lob_context(feature_name: str, lob_data: dict) -> dict:
    """Build LOB context for a feature based on override pages and config keys."""
    context = {}

    # Simple heuristic: check if any LOB's override pages match the feature name
    for lob_name, lob_info in lob_data.items():
        has_relevant_override = False
        relevant_pages = []

        for page in lob_info.get("override_pages", []):
            page_lower = page.lower().replace(".dart", "").replace("_", "")
            feat_lower = feature_name.lower().replace("_", "").replace("sfa_", "").replace("ck_", "")

            if feat_lower in page_lower or page_lower in feat_lower:
                has_relevant_override = True
                relevant_pages.append(page)

        if has_relevant_override:
            context[lob_name] = {
                "has_custom_tests": True,
                "override_pages": relevant_pages,
                "config_keys": lob_info.get("config_keys", []),
                "notes": "",
            }

    return context


def _analyze_git_history(repo_path: str, features: list[dict]) -> dict[str, dict]:
    """Run git log to get file-level history per feature."""
    histories: dict[str, dict] = {}

    for feat in features:
        feat_name = feat["feature_name"]
        file_history = {}

        for src_path in feat["source_paths"]:
            full_path = os.path.join(repo_path, src_path)
            if not os.path.isdir(full_path):
                continue

            try:
                result = subprocess.run(
                    ["git", "log", "--format=%H %ae %ad", "--date=short", "-n", "50", "--", src_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    continue

                # Parse git log
                commits = []
                authors = set()
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 3:
                        commits.append(parts[0])
                        authors.add(parts[1])

                if commits:
                    # Get changed files from the most recent commits
                    file_result = subprocess.run(
                        ["git", "log", "--name-only", "--format=", "-n", "20", "--", src_path],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    for file_line in file_result.stdout.strip().split("\n"):
                        file_line = file_line.strip()
                        if file_line and file_line.startswith(src_path):
                            if file_line not in file_history:
                                file_history[file_line] = {
                                    "last_modified": "",
                                    "commit_count": 0,
                                    "authors": [],
                                }
                            file_history[file_line]["commit_count"] += 1

                    # Set last modified and authors from log
                    for file_path in file_history:
                        if file_path.startswith(src_path):
                            file_history[file_path]["authors"] = list(authors)[:10]
                            if commits:
                                # Get date of most recent commit
                                date_result = subprocess.run(
                                    ["git", "log", "--format=%ad", "--date=short", "-n", "1", "--", file_path],
                                    cwd=repo_path,
                                    capture_output=True,
                                    text=True,
                                    timeout=10,
                                )
                                if date_result.stdout.strip():
                                    file_history[file_path]["last_modified"] = date_result.stdout.strip().split("\n")[0]

            except (subprocess.TimeoutExpired, OSError):
                continue

        if file_history:
            histories[feat_name] = file_history

    return histories


def _fetch_jira_history(repo_path: str, features: list[dict]) -> dict[str, list]:
    """Extract Jira ticket keys from git log messages and fetch details."""
    from reviewer.jira_client import extract_jira_key, get_issue_context

    histories: dict[str, list] = {}

    for feat in features:
        feat_name = feat["feature_name"]
        tickets = []

        for src_path in feat["source_paths"]:
            try:
                result = subprocess.run(
                    ["git", "log", "--format=%s", "-n", "30", "--", src_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode != 0:
                    continue

                seen_keys = set()
                for line in result.stdout.strip().split("\n"):
                    key = extract_jira_key(line)
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        ctx = get_issue_context(key)
                        if ctx.get("summary"):
                            tickets.append({
                                "ticket_key": key,
                                "summary": ctx["summary"],
                                "ticket_type": ctx.get("type", ""),
                                "epic": ctx.get("epic", ""),
                                "status": ctx.get("status", ""),
                                "lobs_affected": [],
                                "figma_links": [u["url"] for u in ctx.get("figma_urls", [])],
                                "acceptance_criteria": ctx.get("acceptance_criteria", []),
                                "commits": [],
                                "branch": "",
                            })
                        if len(tickets) >= 5:
                            break

            except (subprocess.TimeoutExpired, OSError):
                continue

        if tickets:
            histories[feat_name] = tickets

    return histories


if __name__ == "__main__":
    bootstrap()
