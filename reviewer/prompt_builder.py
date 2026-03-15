"""Assemble the 6-section Claude prompt with token budgeting."""

from __future__ import annotations

import logging

from reviewer.figma_client import format_design_specs_for_prompt
from reviewer.git_analyzer import ChangedFile, get_diff_text, order_files_for_review, should_skip_file
from reviewer.lob_mapper import get_sentinel_warnings, map_paths_to_features
from reviewer.registry import get_feature_context

logger = logging.getLogger(__name__)

# Rough chars-to-tokens ratio (conservative)
CHARS_PER_TOKEN = 4
MAX_TOKENS = 100_000
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN  # 400k chars budget
PER_FILE_DIFF_CAP = 300  # lines

SYSTEM_PROMPT = """\
You are a senior Flutter engineer performing a thorough code review on the Sellina AI \
channelkart-flutter codebase.

You deeply understand:
- Injectable/GetIt dependency injection patterns
- Provider state management
- go_router navigation
- ObjectBox local database
- Multi-tenant LOB-driven configuration (each LOB can override base SFA_Generic behavior)
- Dart/Flutter best practices and common pitfalls

Review the PR diff and all provided context carefully. Produce your review in the exact \
format specified in the Review Instructions section."""


def build_prompt(
    jira_context: dict,
    figma_specs: dict | None,
    feature_contexts: dict[str, dict],
    branch_name: str,
    commits: list[dict],
    changed_files: list[ChangedFile],
    pr_body: str = "",
) -> tuple[str, str]:
    """
    Build the 6-section prompt and system prompt.
    Returns (system_prompt, user_prompt).
    Respects token budgeting — skips generated files, caps per-file diffs at 300 lines,
    total prompt under 100k tokens.
    """
    sections: list[str] = []
    total_chars = 0

    # --- Section 1: Jira Ticket Context ---
    s1 = _build_jira_section(jira_context)
    sections.append(s1)
    total_chars += len(s1)

    # --- Section 2: Design Specs (Figma) ---
    s2 = _build_figma_section(figma_specs)
    sections.append(s2)
    total_chars += len(s2)

    # --- Section 3: Historical Registry Context ---
    s3 = _build_registry_section(feature_contexts, changed_files)
    sections.append(s3)
    total_chars += len(s3)

    # --- Section 4: Branch & Commit Context ---
    s4 = _build_branch_section(branch_name, commits)
    sections.append(s4)
    total_chars += len(s4)

    # --- Section 5: Code Diff ---
    remaining_chars = MAX_CHARS - total_chars - 5000  # Reserve 5k for section 6
    s5 = _build_diff_section(changed_files, remaining_chars)
    sections.append(s5)

    # --- Section 6: Review Instructions ---
    s6 = _build_review_instructions()
    sections.append(s6)

    user_prompt = "\n\n---\n\n".join(sections)
    return SYSTEM_PROMPT, user_prompt


def _build_jira_section(ctx: dict) -> str:
    lines = ["## 1. Jira Ticket Context"]

    if not ctx.get("key") or not ctx.get("summary"):
        lines.append("No Jira ticket detected for this PR.")
        return "\n".join(lines)

    lines.append(f"**Ticket:** {ctx['key']}")
    lines.append(f"**Summary:** {ctx.get('summary', '')}")
    lines.append(f"**Type:** {ctx.get('type', '')} | **Status:** {ctx.get('status', '')}")

    if ctx.get("epic"):
        lines.append(f"**Epic:** {ctx['epic']}")

    if ctx.get("description"):
        lines.append(f"\n**Description:**\n{ctx['description']}")

    ac = ctx.get("acceptance_criteria", [])
    if ac:
        lines.append("\n**Acceptance Criteria:**")
        for i, item in enumerate(ac, 1):
            lines.append(f"  {i}. {item}")

    bugs = ctx.get("open_bugs", [])
    if bugs:
        lines.append(f"\n**Open Bugs ({len(bugs)}):**")
        for bug in bugs:
            lines.append(f"  - {bug['key']}: {bug['summary']} [{bug['status']}]")

    return "\n".join(lines)


def _build_figma_section(specs: dict | None) -> str:
    lines = ["## 2. Design Specs (Figma)"]

    if specs is None or not any(specs.values()):
        lines.append("No Figma link found.")
        return "\n".join(lines)

    lines.append(format_design_specs_for_prompt(specs))
    return "\n".join(lines)


def _build_registry_section(
    feature_contexts: dict[str, dict],
    changed_files: list[ChangedFile],
) -> str:
    lines = ["## 3. Historical Registry Context"]

    file_paths = [f.path for f in changed_files]

    # Sentinel warnings
    warnings = get_sentinel_warnings(file_paths)
    if warnings:
        lines.append("### ⚠️ Sentinel Files Changed")
        lines.extend(warnings)
        lines.append("")

    # Feature contexts
    if not feature_contexts:
        lines.append("No feature registry data available (first PR for these paths).")
        return "\n".join(lines)

    lines.append(f"**Features detected:** {', '.join(feature_contexts.keys())}")

    for feat_name, ctx in feature_contexts.items():
        lines.append(f"\n### Feature: {feat_name}")

        if not ctx.get("exists"):
            lines.append("  _No history — first PR for this feature._")
            continue

        # LOB context
        lob_ctx = ctx.get("lob_context", {})
        if lob_ctx:
            lines.append("**LOB-specific behavior:**")
            for lob, data in lob_ctx.items():
                overrides = data.get("override_pages", [])
                notes = data.get("notes", "")
                override_str = f", overrides: {', '.join(overrides)}" if overrides else ""
                notes_str = f" — {notes}" if notes else ""
                lines.append(f"  - **{lob}**: custom_tests={data.get('has_custom_tests', False)}{override_str}{notes_str}")

        # Jira history
        jira_hist = ctx.get("jira_history", [])
        if jira_hist:
            lines.append(f"\n**Recent Jira tickets ({len(jira_hist)}):**")
            for t in jira_hist:
                lines.append(
                    f"  - {t.get('ticket_key', '?')}: {t.get('summary', '')} "
                    f"[{t.get('ticket_type', '')}] — {t.get('status', '')}"
                )

        # Git history
        git_hist = ctx.get("git_file_history", {})
        if git_hist:
            lines.append(f"\n**Recent file changes ({len(git_hist)} files):**")
            for fpath, info in list(git_hist.items())[:10]:
                lines.append(
                    f"  - `{fpath}`: {info.get('commit_count', 0)} commits, "
                    f"last modified {info.get('last_modified', '?')}"
                )

        # Related features
        related = ctx.get("related_features", [])
        if related:
            lines.append(f"\n**Related features:** {', '.join(related)}")

    return "\n".join(lines)


def _build_branch_section(branch_name: str, commits: list[dict]) -> str:
    lines = ["## 4. Branch & Commit Context"]
    lines.append(f"**Branch:** `{branch_name}`")

    if commits:
        lines.append(f"\n**Commits ({len(commits)}):**")
        for c in commits:
            lines.append(f"  - `{c.get('sha', '?')[:8]}` {c.get('message', '')}")
    else:
        lines.append("No commit log available.")

    return "\n".join(lines)


def _build_diff_section(changed_files: list[ChangedFile], max_chars: int) -> str:
    lines = ["## 5. Code Diff"]

    # File list (always full)
    all_paths = [f.path for f in changed_files]
    reviewable = [f for f in changed_files if not should_skip_file(f.path)]
    skipped = [f.path for f in changed_files if should_skip_file(f.path)]

    lines.append(f"**Total files changed:** {len(all_paths)}")
    lines.append(f"**Reviewable files:** {len(reviewable)}")

    if skipped:
        lines.append(f"**Skipped (generated):** {', '.join(skipped)}")

    lines.append("\n**File list:**")
    for f in all_paths:
        lines.append(f"  - `{f}`")

    lines.append("\n### Per-file diffs")

    # Order files for review
    ordered = order_files_for_review(changed_files)

    current_chars = sum(len(line) for line in lines)
    for f in ordered:
        diff_text = get_diff_text(f, max_lines=PER_FILE_DIFF_CAP)
        file_block = f"\n#### `{f.path}` [{f.status}] (+{f.additions}/-{f.deletions})\n```diff\n{diff_text}\n```"

        if current_chars + len(file_block) > max_chars:
            lines.append(
                f"\n... [DIFF TRUNCATED — {len(ordered)} reviewable files total, "
                f"remaining files omitted due to size limit]"
            )
            break

        lines.append(file_block)
        current_chars += len(file_block)

    return "\n".join(lines)


def _build_review_instructions() -> str:
    return """## 6. Review Instructions

Produce your review with EXACTLY the following sections (use ### headers):

### Summary
2-3 sentences: what this PR does, the approach, whether it aligns with the Jira ticket.

### Critical Issues
Issues that MUST be fixed before merge. For each:
- **File:** `path/to/file.dart`
- **Line:** {line number from diff}
- **Issue:** {description}
- **Fix:** {suggested fix}

If none, write "No critical issues found."

### Warnings
Non-blocking concerns (bad practices, potential edge cases, missing error handling). Bulleted list.
If none, write "No warnings."

### LOB Impact
For each LOB that has custom behavior for the affected features, assess:
- **{LOB name}**: SAFE / AT RISK / UNKNOWN — {reason}

If no LOB data available, write "No LOB-specific impact data available."

### Figma Compliance
If Figma specs were provided, for each design element:
- **Expected:** {Figma spec}
- **Found:** {what the code does}
- **Fix:** {correction needed, if any}

If no Figma link, write "No Figma link provided — skipping design compliance check."

### Test Coverage
Assessment of test coverage for the changes. What's tested, what's missing.

### Positive Observations
Highlight good patterns, clean code, thoughtful solutions. 2-3 bullets.

### Merge Recommendation
One of: **APPROVE** / **REQUEST_CHANGES** / **NEEDS_DISCUSSION**
With a 1-sentence rationale."""
