"""Parse unified diff strings into structured ChangedFile objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ChangedFile:
    path: str
    additions: int = 0
    deletions: int = 0
    diff_lines: list[str] = field(default_factory=list)
    status: str = "modified"  # added, modified, deleted, renamed


# Files to skip in reviews
SKIP_PATTERNS = (
    r"\.g\.dart$",
    r"\.mocks\.dart$",
    r"injection\.config\.dart$",
    r"pubspec\.lock$",
    r"\.freezed\.dart$",
)


def should_skip_file(path: str) -> bool:
    """Return True if file should be excluded from review."""
    return any(re.search(p, path) for p in SKIP_PATTERNS)


def parse_unified_diff(diff_text: str) -> list[ChangedFile]:
    """
    Parse a unified diff string (from `git diff` or GitHub API) into ChangedFile objects.
    Handles multi-file diffs with --- a/ and +++ b/ markers.
    """
    files: list[ChangedFile] = []
    current: ChangedFile | None = None
    current_lines: list[str] = []

    for line in diff_text.split("\n"):
        # New file header
        if line.startswith("diff --git"):
            if current is not None:
                current.diff_lines = current_lines
                files.append(current)

            # Extract path from diff --git a/path b/path
            match = re.search(r"diff --git a/(.+?) b/(.+)", line)
            if match:
                path = match.group(2)
            else:
                path = "unknown"

            current = ChangedFile(path=path)
            current_lines = [line]
            continue

        if current is None:
            continue

        current_lines.append(line)

        # Detect file status
        if line.startswith("new file"):
            current.status = "added"
        elif line.startswith("deleted file"):
            current.status = "deleted"
        elif line.startswith("rename from"):
            current.status = "renamed"

        # Count additions/deletions (skip headers)
        if line.startswith("+") and not line.startswith("+++"):
            current.additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.deletions += 1

    # Don't forget the last file
    if current is not None:
        current.diff_lines = current_lines
        files.append(current)

    return files


def extract_commit_log(log_text: str) -> list[dict[str, str]]:
    """
    Parse `git log --oneline` or similar output into structured commits.
    Expected format: <sha> <message>
    """
    commits: list[dict[str, str]] = []
    for line in log_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            commits.append({"sha": parts[0], "message": parts[1]})
        elif len(parts) == 1:
            commits.append({"sha": parts[0], "message": ""})
    return commits


def get_diff_text(changed_file: ChangedFile, max_lines: int = 300) -> str:
    """Get diff text for a single file, capped at max_lines."""
    lines = changed_file.diff_lines
    if len(lines) > max_lines:
        truncated = lines[:max_lines]
        truncated.append(f"\n... [TRUNCATED — {len(lines)} total lines, showing first {max_lines}]")
        return "\n".join(truncated)
    return "\n".join(lines)


def order_files_for_review(files: list[ChangedFile]) -> list[ChangedFile]:
    """
    Order files for review: models → services → providers → screens → widgets → other.
    Skip generated files.
    """
    priority = {
        "model": 0,
        "models": 0,
        "service": 1,
        "services": 1,
        "repository": 1,
        "provider": 2,
        "providers": 2,
        "screen": 3,
        "screens": 3,
        "page": 3,
        "pages": 3,
        "widget": 4,
        "widgets": 4,
    }

    def sort_key(f: ChangedFile) -> int:
        parts = f.path.lower().split("/")
        for part in parts:
            if part in priority:
                return priority[part]
        return 5

    reviewable = [f for f in files if not should_skip_file(f.path)]
    return sorted(reviewable, key=sort_key)
