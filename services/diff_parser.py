"""
Parse GitHub patch strings to determine which lines are valid for inline comments.

GitHub rejects (422) any review comment pointing at a line not present in the diff.
This module acts as the safety gate between Claude's suggested line numbers and the
GitHub API call.
"""

import re
from dataclasses import dataclass, field


@dataclass
class FileDiffMap:
    """Valid commentable line numbers for a single file."""
    right_lines: set[int] = field(default_factory=set)   # new-file line numbers ("+")
    context_lines: set[int] = field(default_factory=set)  # unchanged context lines


def parse_patch(patch: str) -> FileDiffMap:
    """
    Parse a GitHub diff patch string and return the set of valid line numbers.

    Patch format example:
        @@ -10,7 +10,9 @@
         context line         <- right line 10
        -removed line         <- old file only
        +added line 1         <- right line 11
        +added line 2         <- right line 12
         context line         <- right line 13
    """
    result = FileDiffMap()
    if not patch:
        return result

    right_line = 0

    for raw_line in patch.split("\n"):
        if raw_line.startswith("@@"):
            # Extract the new-file start position: +<start>[,<count>]
            m = re.search(r"\+(\d+)(?:,\d+)?", raw_line)
            if m:
                right_line = int(m.group(1)) - 1  # will be incremented on first real line
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            right_line += 1
            result.right_lines.add(right_line)
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            pass  # deleted lines don't advance the right-side counter
        else:
            # Context line: part of the diff window, commentable on the right side
            right_line += 1
            result.context_lines.add(right_line)

    return result


def build_line_maps(pr_files: list[dict]) -> dict[str, FileDiffMap]:
    """Build a {filename: FileDiffMap} mapping for all files in the PR."""
    return {
        f["filename"]: parse_patch(f.get("patch", ""))
        for f in pr_files
        if f.get("filename")
    }


def is_line_valid(line_maps: dict[str, FileDiffMap], path: str, line: int) -> bool:
    """Return True if (path, line) is a valid inline comment target."""
    dm = line_maps.get(path)
    if dm is None:
        return False
    return line in dm.right_lines or line in dm.context_lines


def format_diff_for_review(pr_files: list[dict], max_chars: int = 80_000) -> str:
    """
    Format PR file patches into a clean, annotated diff string for the AI prompt.
    Adds line numbers so Claude can reference them accurately.
    Truncates at max_chars to stay within context limits.
    """
    sections: list[str] = []
    total = 0

    for f in pr_files:
        filename = f.get("filename", "unknown")
        status = f.get("status", "modified")
        patch = f.get("patch", "")

        header = f"\n{'=' * 60}\nFILE: {filename}  [{status.upper()}]\n{'=' * 60}"

        if not patch:
            block = header + "\n(Binary file or no textual diff available)\n"
        else:
            lines = _annotate_patch(patch)
            block = header + "\n" + lines

        if total + len(block) > max_chars:
            sections.append(
                f"\n\n... [DIFF TRUNCATED — {len(pr_files)} files total, "
                f"showing first {len(sections)} due to size limit] ...\n"
            )
            break

        sections.append(block)
        total += len(block)

    return "\n".join(sections)


def _annotate_patch(patch: str) -> str:
    """Add right-side line numbers to each diff line for easier AI reference."""
    output: list[str] = []
    right_line = 0

    for raw_line in patch.split("\n"):
        if raw_line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,\d+)?", raw_line)
            if m:
                right_line = int(m.group(1)) - 1
            output.append(f"       {raw_line}")
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            right_line += 1
            output.append(f"[+{right_line:>4}] {raw_line}")
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            output.append(f"[  DEL] {raw_line}")
        else:
            right_line += 1
            output.append(f"[ {right_line:>4}] {raw_line}")

    return "\n".join(output)
