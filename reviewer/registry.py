"""Read/write/update feature registry JSON files."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from reviewer import config

logger = logging.getLogger(__name__)


def _features_dir() -> str:
    return os.path.join(config.REGISTRY_PATH, "features")


def _feature_path(feature_name: str) -> str:
    return os.path.join(_features_dir(), f"{feature_name}.json")


def load_feature(feature_name: str) -> dict | None:
    """Load a feature JSON. Returns None if not found."""
    path = _feature_path(feature_name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def update_feature(feature_name: str, data: dict) -> None:
    """Write/update a feature JSON file."""
    os.makedirs(_features_dir(), exist_ok=True)
    path = _feature_path(feature_name)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Updated registry: %s", path)


def list_all_features() -> list[str]:
    """List all feature names in the registry."""
    features_dir = _features_dir()
    if not os.path.exists(features_dir):
        return []
    return [
        f.removesuffix(".json")
        for f in sorted(os.listdir(features_dir))
        if f.endswith(".json")
    ]


def add_jira_history(feature_name: str, ticket: dict) -> None:
    """Append a Jira ticket to a feature's history."""
    data = load_feature(feature_name)
    if data is None:
        data = {
            "feature_name": feature_name,
            "source_paths": [],
            "sub_paths": {},
            "lob_context": {},
            "jira_history": [],
            "git_file_history": {},
            "related_features": [],
        }

    history = data.get("jira_history", [])
    # Don't add duplicate tickets
    existing_keys = {h.get("ticket_key") for h in history}
    if ticket.get("ticket_key") not in existing_keys:
        history.append(ticket)
        data["jira_history"] = history

    update_feature(feature_name, data)


def update_git_history(feature_name: str, file_path: str, commit_sha: str, author: str) -> None:
    """Update git file history for a feature."""
    data = load_feature(feature_name)
    if data is None:
        return

    git_history = data.get("git_file_history", {})
    if file_path not in git_history:
        git_history[file_path] = {
            "last_modified": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "commit_count": 1,
            "authors": [author],
        }
    else:
        entry = git_history[file_path]
        entry["last_modified"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entry["commit_count"] = entry.get("commit_count", 0) + 1
        authors = entry.get("authors", [])
        if author not in authors:
            authors.append(author)

    data["git_file_history"] = git_history
    update_feature(feature_name, data)


def get_feature_context(feature_name: str) -> dict:
    """
    Load a feature and return structured context for the AI prompt.
    Returns a dict with all relevant fields, safe to use even if feature doesn't exist.
    """
    data = load_feature(feature_name)
    if data is None:
        return {
            "feature_name": feature_name,
            "exists": False,
            "lob_context": {},
            "jira_history": [],
            "git_file_history": {},
            "related_features": [],
        }

    return {
        "feature_name": feature_name,
        "exists": True,
        "lob_context": data.get("lob_context", {}),
        "jira_history": data.get("jira_history", [])[-5:],  # Last 5
        "git_file_history": dict(
            sorted(
                data.get("git_file_history", {}).items(),
                key=lambda x: x[1].get("last_modified", ""),
                reverse=True,
            )[:10]  # Last 10 most recently modified
        ),
        "related_features": data.get("related_features", []),
    }
