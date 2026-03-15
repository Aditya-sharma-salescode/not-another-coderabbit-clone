"""Tests for prompt_builder — token budgeting and section assembly."""

from reviewer.git_analyzer import ChangedFile
from reviewer.prompt_builder import build_prompt


def _make_changed_file(path: str, additions: int = 5, lines: int = 20) -> ChangedFile:
    return ChangedFile(
        path=path,
        additions=additions,
        deletions=0,
        diff_lines=[f"+line {i}" for i in range(lines)],
    )


def test_build_prompt_returns_system_and_user():
    system, user = build_prompt(
        jira_context={"key": "CSLC-100", "summary": "Test ticket"},
        figma_specs=None,
        feature_contexts={},
        branch_name="CSLC-100-test",
        commits=[{"sha": "abc123", "message": "test commit"}],
        changed_files=[_make_changed_file("lib/features/cart/model/cart.dart")],
    )
    assert isinstance(system, str)
    assert isinstance(user, str)
    assert "Flutter" in system
    assert "Jira Ticket Context" in user


def test_build_prompt_six_sections():
    _, user = build_prompt(
        jira_context={"key": "CSLC-100", "summary": "Test"},
        figma_specs=None,
        feature_contexts={},
        branch_name="CSLC-100-test",
        commits=[],
        changed_files=[_make_changed_file("lib/features/cart/model/cart.dart")],
    )
    assert "## 1. Jira Ticket Context" in user
    assert "## 2. Design Specs (Figma)" in user
    assert "## 3. Historical Registry Context" in user
    assert "## 4. Branch & Commit Context" in user
    assert "## 5. Code Diff" in user
    assert "## 6. Review Instructions" in user


def test_build_prompt_no_jira():
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="feature-test",
        commits=[],
        changed_files=[_make_changed_file("lib/features/cart/model/cart.dart")],
    )
    assert "No Jira ticket detected" in user


def test_build_prompt_no_figma():
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="test",
        commits=[],
        changed_files=[],
    )
    assert "No Figma link found" in user


def test_build_prompt_with_figma_specs():
    specs = {
        "layout": [{"name": "Button", "type": "FRAME", "width": 200, "height": 48}],
        "colors": [{"node": "Background", "hex": "#FF5722", "token": "", "opacity": 1.0}],
        "typography": [{"node": "Title", "fontFamily": "Roboto", "fontSize": 16, "fontWeight": 700, "lineHeightPx": 24, "letterSpacing": 0, "heightRatio": 1.5}],
        "components": [],
    }
    _, user = build_prompt(
        jira_context={},
        figma_specs=specs,
        feature_contexts={},
        branch_name="test",
        commits=[],
        changed_files=[],
    )
    assert "#FF5722" in user
    assert "Roboto" in user
    assert "EdgeInsets" in user


def test_build_prompt_with_feature_context():
    feature_ctx = {
        "cart": {
            "feature_name": "cart",
            "exists": True,
            "lob_context": {
                "cokearg_sfa": {
                    "has_custom_tests": True,
                    "override_pages": ["orderplacing.dart"],
                    "notes": "Custom order",
                }
            },
            "jira_history": [
                {"ticket_key": "COCA-850", "summary": "Cart fix", "ticket_type": "Bug", "status": "Done"}
            ],
            "git_file_history": {},
            "related_features": ["catalogue"],
        }
    }
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts=feature_ctx,
        branch_name="test",
        commits=[],
        changed_files=[_make_changed_file("lib/features/cart/model/cart.dart")],
    )
    assert "cokearg_sfa" in user
    assert "COCA-850" in user
    assert "catalogue" in user


def test_build_prompt_review_instructions_format():
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="test",
        commits=[],
        changed_files=[],
    )
    # Verify all required review sections are mentioned
    assert "### Summary" in user
    assert "### Critical Issues" in user
    assert "### Warnings" in user
    assert "### LOB Impact" in user
    assert "### Figma Compliance" in user
    assert "### Test Coverage" in user
    assert "### Positive Observations" in user
    assert "### Merge Recommendation" in user
    assert "APPROVE" in user
    assert "REQUEST_CHANGES" in user
    assert "NEEDS_DISCUSSION" in user


def test_build_prompt_skips_generated_files():
    files = [
        _make_changed_file("lib/features/cart/model/cart.dart"),
        _make_changed_file("lib/features/cart/model/cart.g.dart"),
        _make_changed_file("lib/features/cart/model/cart.mocks.dart"),
    ]
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="test",
        commits=[],
        changed_files=files,
    )
    assert "cart.g.dart" in user  # Listed in file list
    assert "Skipped (generated)" in user


def test_build_prompt_token_budget():
    # Create many large files to test truncation
    files = [
        _make_changed_file(f"lib/features/test/file_{i}.dart", additions=300, lines=400)
        for i in range(200)
    ]
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="test",
        commits=[],
        changed_files=files,
    )
    # Should be under 400k chars (100k tokens * 4)
    assert len(user) < 400_000
    assert "TRUNCATED" in user


def test_build_prompt_with_commits():
    commits = [
        {"sha": "abc123", "message": "fix cart state bug"},
        {"sha": "def456", "message": "add unit tests"},
    ]
    _, user = build_prompt(
        jira_context={},
        figma_specs=None,
        feature_contexts={},
        branch_name="COCA-850-cart-state",
        commits=commits,
        changed_files=[],
    )
    assert "abc123" in user
    assert "fix cart state bug" in user
    assert "COCA-850-cart-state" in user
