"""Tests for registry — JSON read/write/update operations."""

import json
import os
import tempfile

import pytest

from reviewer import config
from reviewer.registry import (
    add_jira_history,
    get_feature_context,
    list_all_features,
    load_feature,
    update_feature,
    update_git_history,
)


@pytest.fixture
def temp_registry(tmp_path):
    """Create a temporary registry directory and set it as the config path."""
    features_dir = tmp_path / "features"
    features_dir.mkdir()

    # Save and restore original path
    original = config.REGISTRY_PATH
    config.REGISTRY_PATH = str(tmp_path)
    yield tmp_path
    config.REGISTRY_PATH = original


def test_load_feature_not_found(temp_registry):
    result = load_feature("nonexistent")
    assert result is None


def test_update_and_load_feature(temp_registry):
    data = {
        "feature_name": "cart",
        "source_paths": ["lib/features/cart/"],
        "sub_paths": {},
        "lob_context": {},
        "jira_history": [],
        "git_file_history": {},
        "related_features": ["catalogue"],
    }
    update_feature("cart", data)
    loaded = load_feature("cart")

    assert loaded is not None
    assert loaded["feature_name"] == "cart"
    assert loaded["related_features"] == ["catalogue"]
    assert "last_updated" in loaded


def test_list_all_features(temp_registry):
    for name in ["cart", "auth", "catalogue"]:
        update_feature(name, {"feature_name": name})

    features = list_all_features()
    assert sorted(features) == ["auth", "cart", "catalogue"]


def test_list_all_features_empty(temp_registry):
    features = list_all_features()
    assert features == []


def test_add_jira_history_new_feature(temp_registry):
    ticket = {
        "ticket_key": "COCA-850",
        "summary": "Cart state fix",
        "ticket_type": "Bug",
        "status": "Done",
    }
    add_jira_history("cart", ticket)

    loaded = load_feature("cart")
    assert loaded is not None
    assert len(loaded["jira_history"]) == 1
    assert loaded["jira_history"][0]["ticket_key"] == "COCA-850"


def test_add_jira_history_existing_feature(temp_registry):
    update_feature("cart", {
        "feature_name": "cart",
        "jira_history": [{"ticket_key": "COCA-800", "summary": "old ticket"}],
    })

    add_jira_history("cart", {"ticket_key": "COCA-850", "summary": "new ticket"})

    loaded = load_feature("cart")
    assert len(loaded["jira_history"]) == 2


def test_add_jira_history_no_duplicates(temp_registry):
    add_jira_history("cart", {"ticket_key": "COCA-850", "summary": "fix"})
    add_jira_history("cart", {"ticket_key": "COCA-850", "summary": "fix again"})

    loaded = load_feature("cart")
    assert len(loaded["jira_history"]) == 1


def test_add_jira_history_stores_all(temp_registry):
    for i in range(25):
        add_jira_history("cart", {"ticket_key": f"COCA-{i}", "summary": f"ticket {i}"})

    loaded = load_feature("cart")
    # Full history preserved in storage — prompt builder slices for Claude
    assert len(loaded["jira_history"]) == 25
    assert loaded["jira_history"][0]["ticket_key"] == "COCA-0"
    assert loaded["jira_history"][-1]["ticket_key"] == "COCA-24"


def test_update_git_history(temp_registry):
    update_feature("cart", {
        "feature_name": "cart",
        "git_file_history": {},
    })

    update_git_history("cart", "lib/features/cart/model/cart.dart", "abc123", "dev@test.com")

    loaded = load_feature("cart")
    history = loaded["git_file_history"]
    assert "lib/features/cart/model/cart.dart" in history
    entry = history["lib/features/cart/model/cart.dart"]
    assert entry["commit_count"] == 1
    assert "dev@test.com" in entry["authors"]


def test_update_git_history_increments(temp_registry):
    update_feature("cart", {
        "feature_name": "cart",
        "git_file_history": {
            "lib/features/cart/model/cart.dart": {
                "last_modified": "2026-01-01",
                "commit_count": 5,
                "authors": ["dev@test.com"],
            }
        },
    })

    update_git_history("cart", "lib/features/cart/model/cart.dart", "def456", "other@test.com")

    loaded = load_feature("cart")
    entry = loaded["git_file_history"]["lib/features/cart/model/cart.dart"]
    assert entry["commit_count"] == 6
    assert "other@test.com" in entry["authors"]


def test_get_feature_context_exists(temp_registry):
    update_feature("cart", {
        "feature_name": "cart",
        "lob_context": {"cokearg_sfa": {"has_custom_tests": True}},
        "jira_history": [{"ticket_key": f"COCA-{i}"} for i in range(10)],
        "git_file_history": {},
        "related_features": ["catalogue"],
    })

    ctx = get_feature_context("cart")
    assert ctx["exists"] is True
    assert ctx["feature_name"] == "cart"
    assert len(ctx["jira_history"]) == 5  # Capped at last 5
    assert ctx["related_features"] == ["catalogue"]


def test_get_feature_context_not_exists(temp_registry):
    ctx = get_feature_context("nonexistent")
    assert ctx["exists"] is False
    assert ctx["feature_name"] == "nonexistent"
    assert ctx["jira_history"] == []


def test_update_feature_sets_last_updated(temp_registry):
    update_feature("cart", {"feature_name": "cart"})
    loaded = load_feature("cart")
    assert "last_updated" in loaded
    assert "T" in loaded["last_updated"]  # ISO format


def test_feature_json_is_valid(temp_registry):
    update_feature("cart", {
        "feature_name": "cart",
        "source_paths": ["lib/features/cart/"],
    })

    # Read raw JSON and verify it's valid
    path = os.path.join(str(temp_registry), "features", "cart.json")
    with open(path) as f:
        data = json.load(f)
    assert data["feature_name"] == "cart"
