"""Jira REST API client — optional integration for ticket context."""

import base64
import logging
import re

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Matches standard Jira ticket IDs like PROJ-123, BACKEND-456
TICKET_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def extract_ticket_id(text: str) -> str | None:
    """Extract the first Jira ticket ID found in a string (branch name, PR title, body)."""
    match = TICKET_PATTERN.search(text or "")
    return match.group(1) if match else None


async def get_ticket_context(ticket_id: str) -> str:
    """
    Fetch Jira ticket details and return a formatted context string.
    Returns empty string if Jira is not configured or ticket not found.
    """
    if not settings.jira_enabled:
        return ""

    auth = base64.b64encode(
        f"{settings.jira_email}:{settings.jira_api_token}".encode()
    ).decode()

    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}"
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 404:
                logger.warning("Jira ticket %s not found", ticket_id)
                return f"Jira ticket {ticket_id} not found."
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("Failed to fetch Jira ticket %s: %s", ticket_id, e)
        return ""

    fields = data.get("fields", {})
    summary = fields.get("summary", "")
    issue_type = fields.get("issuetype", {}).get("name", "")
    priority = fields.get("priority", {}).get("name", "")
    status = fields.get("status", {}).get("name", "")
    description = _extract_text(fields.get("description")) or "No description provided."

    # Acceptance criteria — commonly in a custom field; try common field names
    ac_text = ""
    for key in ("customfield_10016", "customfield_10014", "customfield_10010"):
        raw = fields.get(key)
        if raw and isinstance(raw, (str, dict)):
            ac_text = _extract_text(raw) if isinstance(raw, dict) else str(raw)
            if ac_text:
                break

    lines = [
        f"Jira Ticket: {ticket_id}",
        f"Summary: {summary}",
        f"Type: {issue_type} | Priority: {priority} | Status: {status}",
        "",
        "Description:",
        description,
    ]
    if ac_text:
        lines += ["", "Acceptance Criteria:", ac_text]

    return "\n".join(lines)


def _extract_text(node: dict | str | None) -> str:
    """
    Recursively extract plain text from Atlassian Document Format (ADF) nodes.
    Falls back gracefully for plain strings.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = [_extract_text(child) for child in node.get("content", [])]
        separator = "\n" if node.get("type") in ("paragraph", "bulletList", "listItem") else " "
        return separator.join(p for p in parts if p)
    return ""
