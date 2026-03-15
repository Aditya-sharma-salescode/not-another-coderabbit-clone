"""Tests for kb_query tool executors — no Claude API calls needed."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from reviewer import config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry_dir(tmp_path):
    """Set up a minimal registry with 2 features, 2 LOBs, and an index."""
    features_dir = tmp_path / "features"
    features_dir.mkdir()

    # Feature 1: order_checkout
    (features_dir / "order_checkout.json").write_text(json.dumps({
        "feature_name": "order_checkout",
        "source_paths": ["lib/features/order_checkout/"],
        "sub_paths": {},
        "lob_context": {
            "cokearg_sfa": {
                "override_pages": ["orderFeedback.dart", "orderHelperFunctions.dart"],
            }
        },
        "jira_history": [
            {"ticket_key": "COCA-100", "summary": "Order flow fix", "status": "Done"},
            {"ticket_key": "COCA-200", "summary": "Checkout revamp", "status": "In Progress"},
        ],
        "git_file_history": {
            "lib/features/order_checkout/view/order_page.dart": {
                "last_modified": "2026-02-01",
                "commit_count": 5,
                "authors": ["alice@example.com"],
            },
            "lib/features/order_checkout/view/orderFeedback.dart": {
                "last_modified": "2026-03-10",
                "commit_count": 3,
                "authors": ["bob@example.com", "alice@example.com"],
            },
        },
        "related_features": ["cart"],
        "last_updated": "2026-03-10T00:00:00+00:00",
    }))

    # Feature 2: cart
    (features_dir / "cart.json").write_text(json.dumps({
        "feature_name": "cart",
        "source_paths": ["lib/features/cart/"],
        "sub_paths": {},
        "lob_context": {},
        "jira_history": [],
        "git_file_history": {
            "lib/features/cart/model/cart.dart": {
                "last_modified": "2025-12-01",
                "commit_count": 2,
                "authors": ["charlie@example.com"],
            },
        },
        "related_features": [],
        "last_updated": "2025-12-01T00:00:00+00:00",
    }))

    # index.json
    (tmp_path / "index.json").write_text(json.dumps({
        "path_to_feature": {
            "lib/features/order_checkout/": "order_checkout",
            "lib/features/cart/": "cart",
            "lib/go_router.dart": "_routing",
        },
        "sentinel_paths": {
            "_routing": "Affects all navigation — review carefully",
        },
    }))

    # lob_index.json
    (tmp_path / "lob_index.json").write_text(json.dumps({
        "lobs": {
            "cokearg_sfa": {
                "enabled_features": ["order_checkout"],
                "override_pages": ["orderFeedback.dart"],
                "overrides": {
                    "order_checkout": {
                        "override_pages": ["orderFeedback.dart", "orderHelperFunctions.dart"],
                    }
                },
            },
            "unnati": {
                "enabled_features": ["cart"],
                "override_pages": [],
                "feature_overrides": {},
            },
        }
    }))

    config.REGISTRY_PATH = str(tmp_path)
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Helper to call execute_tool with the tmp registry
# ---------------------------------------------------------------------------

def call_tool(name: str, args: dict, registry_path: str) -> dict:
    from reviewer.kb_query import execute_tool
    result = execute_tool(name, args, registry_path)
    return json.loads(result)


# ---------------------------------------------------------------------------
# list_features
# ---------------------------------------------------------------------------

class TestListFeatures:
    def test_returns_all_features(self, registry_dir):
        result = call_tool("list_features", {}, registry_dir)
        assert set(result["features"]) == {"order_checkout", "cart"}
        assert result["count"] == 2

    def test_empty_registry(self, tmp_path):
        config.REGISTRY_PATH = str(tmp_path)
        result = call_tool("list_features", {}, str(tmp_path))
        assert result["features"] == []
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# get_feature
# ---------------------------------------------------------------------------

class TestGetFeature:
    def test_returns_feature_data(self, registry_dir):
        result = call_tool("get_feature", {"feature_name": "order_checkout"}, registry_dir)
        assert result["feature_name"] == "order_checkout"
        assert len(result["jira_history"]) == 2
        assert "git_file_history" in result

    def test_missing_feature(self, registry_dir):
        result = call_tool("get_feature", {"feature_name": "nonexistent"}, registry_dir)
        assert "error" in result
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# search_feature_by_path
# ---------------------------------------------------------------------------

class TestSearchFeatureByPath:
    def test_finds_feature(self, registry_dir):
        result = call_tool(
            "search_feature_by_path",
            {"file_path": "lib/features/order_checkout/view/order_page.dart"},
            registry_dir,
        )
        assert result["feature"] == "order_checkout"
        assert result["is_sentinel"] is False

    def test_sentinel_path(self, registry_dir):
        result = call_tool(
            "search_feature_by_path",
            {"file_path": "lib/go_router.dart"},
            registry_dir,
        )
        assert result["feature"] == "_routing"
        assert result["is_sentinel"] is True
        assert "navigation" in result["sentinel_warning"].lower()

    def test_unknown_path(self, registry_dir):
        result = call_tool(
            "search_feature_by_path",
            {"file_path": "lib/some/random/file.dart"},
            registry_dir,
        )
        assert result["feature"] is None


# ---------------------------------------------------------------------------
# list_lobs
# ---------------------------------------------------------------------------

class TestListLobs:
    def test_returns_all_lobs(self, registry_dir):
        result = call_tool("list_lobs", {}, registry_dir)
        assert set(result["lobs"]) == {"cokearg_sfa", "unnati"}
        assert result["count"] == 2


# ---------------------------------------------------------------------------
# get_lob
# ---------------------------------------------------------------------------

class TestGetLob:
    def test_returns_lob_data(self, registry_dir):
        result = call_tool("get_lob", {"lob_name": "cokearg_sfa"}, registry_dir)
        assert "override_pages" in result
        assert "orderFeedback.dart" in result["override_pages"]

    def test_case_insensitive(self, registry_dir):
        result = call_tool("get_lob", {"lob_name": "COKEARG_SFA"}, registry_dir)
        assert "error" not in result

    def test_missing_lob(self, registry_dir):
        result = call_tool("get_lob", {"lob_name": "unknown_lob"}, registry_dir)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_lob_overrides_for_feature
# ---------------------------------------------------------------------------

class TestGetLobOverrides:
    def test_finds_overrides(self, registry_dir):
        result = call_tool(
            "get_lob_overrides_for_feature",
            {"feature_name": "order_checkout"},
            registry_dir,
        )
        assert result["feature"] == "order_checkout"
        lob_names = [item["lob"] for item in result["lobs_with_overrides"]]
        assert "cokearg_sfa" in lob_names
        assert result["count"] >= 1

    def test_no_overrides(self, registry_dir):
        # cart has no LOB overrides in lob_index
        result = call_tool(
            "get_lob_overrides_for_feature",
            {"feature_name": "cart"},
            registry_dir,
        )
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# who_changed
# ---------------------------------------------------------------------------

class TestWhoChanged:
    def test_all_authors(self, registry_dir):
        result = call_tool("who_changed", {"feature_name": "order_checkout"}, registry_dir)
        assert "alice@example.com" in result["all_authors"]
        assert "bob@example.com" in result["all_authors"]
        assert result["most_recent_change"] == "2026-03-10"

    def test_lob_filter_narrows_files(self, registry_dir):
        result = call_tool(
            "who_changed",
            {"feature_name": "order_checkout", "lob_name": "cokearg_sfa"},
            registry_dir,
        )
        # Should include orderFeedback.dart (matches "orderFeedback" in override_pages)
        file_names = [f["file"] for f in result["files"]]
        assert any("orderFeedback" in f for f in file_names)

    def test_missing_feature(self, registry_dir):
        result = call_tool("who_changed", {"feature_name": "ghost_feature"}, registry_dir)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_recent_changes
# ---------------------------------------------------------------------------

class TestGetRecentChanges:
    def test_recent_window_filters(self, registry_dir):
        # order_checkout has a file changed 2026-03-10 and one on 2026-02-01
        # With 30-day window from 2026-03-15, only the March file should appear
        result = call_tool(
            "get_recent_changes",
            {"feature_name": "order_checkout", "days": 30},
            registry_dir,
        )
        files = [f["file"] for f in result["files_changed"]]
        assert any("orderFeedback" in f for f in files)
        # order_page.dart was last modified 2026-02-01, outside 30-day window
        assert not any("order_page" in f for f in files)

    def test_wide_window_returns_all(self, registry_dir):
        result = call_tool(
            "get_recent_changes",
            {"feature_name": "order_checkout", "days": 365},
            registry_dir,
        )
        assert result["count"] == 2

    def test_missing_feature(self, registry_dir):
        result = call_tool(
            "get_recent_changes",
            {"feature_name": "no_such_feature", "days": 90},
            registry_dir,
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# get_sentinel_info
# ---------------------------------------------------------------------------

class TestGetSentinelInfo:
    def test_returns_sentinels(self, registry_dir):
        result = call_tool("get_sentinel_info", {}, registry_dir)
        assert result["count"] >= 1
        paths = [s["file_path"] for s in result["sentinel_paths"]]
        assert "lib/go_router.dart" in paths

    def test_sentinel_has_impact(self, registry_dir):
        result = call_tool("get_sentinel_info", {}, registry_dir)
        for s in result["sentinel_paths"]:
            assert s["impact"]  # non-empty


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

class TestUnknownTool:
    def test_unknown_tool_returns_error(self, registry_dir):
        result = call_tool("does_not_exist", {}, registry_dir)
        assert "error" in result
        assert "Unknown tool" in result["error"]
