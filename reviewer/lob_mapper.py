"""Map file paths to features and LOBs via the registry index."""

from __future__ import annotations

import json
import logging
import os

from reviewer import config

logger = logging.getLogger(__name__)


def _index_path() -> str:
    return os.path.join(config.REGISTRY_PATH, "index.json")


def _lob_index_path() -> str:
    return os.path.join(config.REGISTRY_PATH, "lob_index.json")


def load_index() -> dict:
    """Load registry/index.json."""
    path = _index_path()
    if not os.path.exists(path):
        logger.warning("Registry index not found at %s", path)
        return {}
    with open(path) as f:
        return json.load(f)


def load_lob_index() -> dict:
    """Load registry/lob_index.json."""
    path = _lob_index_path()
    if not os.path.exists(path):
        logger.warning("LOB index not found at %s", path)
        return {}
    with open(path) as f:
        return json.load(f)


def map_path_to_feature(file_path: str, index: dict | None = None) -> str | None:
    """
    Map a file path to a feature name using longest prefix match.
    Returns None if no match found.
    """
    if index is None:
        index = load_index()

    path_to_feature = index.get("path_to_feature", {})
    best_match: str | None = None
    best_len = 0

    for prefix, feature_name in path_to_feature.items():
        if file_path.startswith(prefix) and len(prefix) > best_len:
            best_match = feature_name
            best_len = len(prefix)

    return best_match


def map_paths_to_features(file_paths: list[str]) -> dict[str, list[str]]:
    """
    Map a list of file paths to features.
    Returns {feature_name: [file_paths]}.
    Unknown paths are grouped under '_unknown'.
    """
    index = load_index()
    result: dict[str, list[str]] = {}

    for path in file_paths:
        feature = map_path_to_feature(path, index) or "_unknown"
        result.setdefault(feature, []).append(path)

    return result


def is_sentinel_path(file_path: str, index: dict | None = None) -> str | None:
    """
    Check if a file path matches a sentinel path.
    Returns the warning message if it's sentinel, None otherwise.
    """
    if index is None:
        index = load_index()

    sentinel_paths = index.get("sentinel_paths", {})
    path_to_feature = index.get("path_to_feature", {})

    # Check if the file matches any sentinel path
    for prefix, feature_name in path_to_feature.items():
        if file_path.startswith(prefix) and feature_name in sentinel_paths:
            return sentinel_paths[feature_name]

    return None


def get_sentinel_warnings(file_paths: list[str]) -> list[str]:
    """
    Check all file paths for sentinel matches.
    Returns list of warning strings for any matches.
    """
    index = load_index()
    warnings = []
    seen = set()

    for path in file_paths:
        warning = is_sentinel_path(path, index)
        if warning and warning not in seen:
            seen.add(warning)
            warnings.append(f"⚠️ SENTINEL FILE: `{path}` — {warning}")

    return warnings


def get_affected_lobs(feature_name: str, lob_index: dict | None = None) -> list[dict]:
    """
    Given a feature name, return the LOBs that have custom overrides for it.
    Each entry: {lob, has_custom_tests, override_pages, notes}.
    """
    if lob_index is None:
        lob_index = load_lob_index()

    affected = []
    for lob_name, lob_data in lob_index.get("lobs", {}).items():
        overrides = lob_data.get("overrides", {})
        if feature_name in overrides:
            entry = overrides[feature_name].copy()
            entry["lob"] = lob_name
            affected.append(entry)

    return affected
