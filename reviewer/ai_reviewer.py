"""Call Claude via Anthropic API, parse response, format as GitHub comment."""

from __future__ import annotations

import logging
import re

import anthropic

from reviewer import config
from reviewer.github_client import REVIEW_MARKER

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 4096


def run_review(system_prompt: str, user_prompt: str) -> str:
    """
    Send the assembled prompt to Claude and return the raw review text.
    Uses claude-sonnet-4-6 with extended thinking for deep analysis.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    logger.info(
        "Sending review to Claude (%s) — prompt ~%d chars (~%d tokens)",
        MODEL,
        len(user_prompt),
        len(user_prompt) // 4,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from response
    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    review_text = "\n".join(text_parts)
    logger.info("Claude review complete — %d chars", len(review_text))

    return review_text


def parse_review_sections(review_text: str) -> dict[str, str]:
    """
    Parse Claude's response by ### headers into named sections.
    Returns {section_name: content}.
    """
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_lines: list[str] = []

    for line in review_text.split("\n"):
        header_match = re.match(r"^###\s+(.+)$", line)
        if header_match:
            # Save previous section
            if current_lines:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = header_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


def extract_merge_recommendation(sections: dict[str, str]) -> str:
    """Extract the merge recommendation from parsed sections."""
    rec_section = sections.get("Merge Recommendation", "")
    for keyword in ("APPROVE", "REQUEST_CHANGES", "NEEDS_DISCUSSION"):
        if keyword in rec_section.upper().replace(" ", "_"):
            return keyword
    return "NEEDS_DISCUSSION"


def format_github_comment(review_text: str, sentinel_warnings: list[str] | None = None) -> str:
    """
    Format the review text as a GitHub PR comment with the AI reviewer marker.
    """
    parts = [REVIEW_MARKER, ""]

    # Sentinel banner
    if sentinel_warnings:
        parts.append("## 🚨 CRITICAL: Sentinel Files Changed")
        parts.extend(sentinel_warnings)
        parts.append("")
        parts.append("---")
        parts.append("")

    parts.append("## 🤖 AI PR Review")
    parts.append("")
    parts.append(review_text)
    parts.append("")
    parts.append("---")
    parts.append(
        "*Reviewed by [pr-reviewer](https://github.com) using Claude (claude-sonnet-4-6)*"
    )

    return "\n".join(parts)
