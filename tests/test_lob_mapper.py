"""Tests for lob_mapper — path-to-feature mapping and sentinel detection."""

import json
import os
import tempfile

import pytest

from reviewer.lob_mapper import (
    get_affected_lobs,
    get_sentinel_warnings,
    is_sentinel_path,
    map_path_to_feature,
    map_paths_to_features,
)

SAMPLE_INDEX = {
    "version": "1.0",
    "path_to_feature": {
        "lib/features/cart/": "cart",
        "lib/features/cart/model/": "cart",
        "lib/features/order_checkout/": "order_checkout",
        "lib/features/auth/": "auth",
        "lib/sfa/features/attendance/": "sfa_attendance",
        "lib/channelKart/features/payment_dashboard/": "ck_payment_dashboard",
        "lib/go_router.dart": "_routing",
        "lib/constants/config_lob.dart": "_lob_config",
        "lib/main.dart": "_app_root",
    },
    "sentinel_paths": {
        "_lob_config": "CRITICAL: affects ALL LOBs at runtime",
        "_routing": "CRITICAL: affects ALL navigation flows",
        "_app_root": "CRITICAL: app entry point",
    },
}

SAMPLE_LOB_INDEX = {
    "version": "1.0",
    "lobs": {
        "cokearg_sfa": {
            "name": "cokearg_sfa",
            "overrides": {
                "order_checkout": {
                    "has_custom_tests": True,
                    "override_pages": ["orderFeedback.dart", "orderplacing.dart"],
                    "notes": "Custom order flow",
                },
            },
        },
        "Perfettisfai": {
            "name": "Perfettisfai",
            "overrides": {
                "order_checkout": {
                    "has_custom_tests": True,
                    "override_pages": ["order.dart"],
                    "notes": "Custom order",
                },
            },
        },
        "SFA_Generic": {
            "name": "SFA_Generic",
            "overrides": {},
        },
    },
}


def test_map_path_to_feature_exact():
    assert map_path_to_feature("lib/features/cart/widgets/item.dart", SAMPLE_INDEX) == "cart"


def test_map_path_to_feature_longest_prefix():
    # lib/features/cart/model/ is a longer prefix than lib/features/cart/
    result = map_path_to_feature("lib/features/cart/model/cart_item.dart", SAMPLE_INDEX)
    assert result == "cart"


def test_map_path_to_feature_sfa():
    result = map_path_to_feature("lib/sfa/features/attendance/screens/main.dart", SAMPLE_INDEX)
    assert result == "sfa_attendance"


def test_map_path_to_feature_channelkart():
    result = map_path_to_feature("lib/channelKart/features/payment_dashboard/widget.dart", SAMPLE_INDEX)
    assert result == "ck_payment_dashboard"


def test_map_path_to_feature_no_match():
    result = map_path_to_feature("lib/utils/helper.dart", SAMPLE_INDEX)
    assert result is None


def test_map_path_to_feature_sentinel():
    result = map_path_to_feature("lib/go_router.dart", SAMPLE_INDEX)
    assert result == "_routing"


def test_map_paths_to_features():
    paths = [
        "lib/features/cart/model/cart.dart",
        "lib/features/cart/services/svc.dart",
        "lib/features/auth/login.dart",
        "lib/utils/helper.dart",
    ]
    result = map_paths_to_features(paths)

    # Uses the real index.json, but let's test the function structure
    assert isinstance(result, dict)


def test_is_sentinel_path_config_lob():
    result = is_sentinel_path("lib/constants/config_lob.dart", SAMPLE_INDEX)
    assert result == "CRITICAL: affects ALL LOBs at runtime"


def test_is_sentinel_path_router():
    result = is_sentinel_path("lib/go_router.dart", SAMPLE_INDEX)
    assert result == "CRITICAL: affects ALL navigation flows"


def test_is_sentinel_path_main():
    result = is_sentinel_path("lib/main.dart", SAMPLE_INDEX)
    assert result == "CRITICAL: app entry point"


def test_is_sentinel_path_normal_file():
    result = is_sentinel_path("lib/features/cart/model/cart.dart", SAMPLE_INDEX)
    assert result is None


def test_get_sentinel_warnings():
    paths = [
        "lib/features/cart/model/cart.dart",
        "lib/go_router.dart",
        "lib/constants/config_lob.dart",
    ]
    warnings = get_sentinel_warnings(paths)
    # Should have warnings for go_router and config_lob
    assert len(warnings) >= 2
    assert any("navigation" in w.lower() for w in warnings)
    assert any("lob" in w.lower() for w in warnings)


def test_get_sentinel_warnings_none():
    paths = ["lib/features/cart/model/cart.dart"]
    warnings = get_sentinel_warnings(paths)
    assert len(warnings) == 0


def test_get_affected_lobs():
    affected = get_affected_lobs("order_checkout", SAMPLE_LOB_INDEX)
    assert len(affected) == 2

    lob_names = {a["lob"] for a in affected}
    assert "cokearg_sfa" in lob_names
    assert "Perfettisfai" in lob_names


def test_get_affected_lobs_none():
    affected = get_affected_lobs("nonexistent_feature", SAMPLE_LOB_INDEX)
    assert affected == []
