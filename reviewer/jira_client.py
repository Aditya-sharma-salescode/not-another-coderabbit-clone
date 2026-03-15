"""Jira Cloud REST API v3 client — fetch tickets, parse ADF, search bugs."""

from __future__ import annotations

import base64
import logging
import re
import time

import httpx

from reviewer import config

logger = logging.getLogger(__name__)

# Matches Jira ticket IDs like CSLC-235, COCA-850
TICKET_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in config.JIRA_PROJECTS) + r")-(\d+)\b",
    re.IGNORECASE,
)

# Figma URL regex
FIGMA_URL_PATTERN = re.compile(
    r"https://www\.figma\.com/(design|file)/([A-Za-z0-9_-]+)/[^?\s]*"
    r"(?:\?[^\s]*node-id=([\d:%-]+))?"
)

MAX_RETRIES = 3
RETRY_STATUSES = (429, 503)


def _auth_header() -> str:
    creds = f"{config.JIRA_EMAIL}:{config.JIRA_API_TOKEN}"
    return f"Basic {base64.b64encode(creds.encode()).decode()}"


def _jira_headers() -> dict[str, str]:
    return {
        "Authorization": _auth_header(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _jira_url(path: str) -> str:
    return f"{config.JIRA_BASE_URL.rstrip('/')}/rest/api/3{path}"


def _request_with_retry(
    method: str, url: str, headers: dict, **kwargs
) -> httpx.Response | None:
    """Make an HTTP request with retry on 429/503."""
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=20) as client:
                r = client.request(method, url, headers=headers, **kwargs)
                if r.status_code in RETRY_STATUSES:
                    wait = min(2 ** attempt * 2, 30)
                    logger.warning(
                        "Jira returned %d, retrying in %ds (attempt %d/%d)",
                        r.status_code, wait, attempt + 1, MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                return r
        except httpx.HTTPError as e:
            logger.warning("Jira request failed: %s (attempt %d/%d)", e, attempt + 1, MAX_RETRIES)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return None


def extract_jira_key(text: str) -> str | None:
    """Extract the first Jira ticket key from text (branch name, PR title, etc.)."""
    # Normalize to uppercase for matching
    match = TICKET_PATTERN.search(text.upper() if text else "")
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return None


def get_issue(ticket_key: str) -> dict | None:
    """Fetch a Jira issue. Returns None on failure (never crashes)."""
    if not config.jira_enabled():
        logger.info("Jira not configured, skipping ticket fetch")
        return None

    url = _jira_url(f"/issue/{ticket_key}")
    r = _request_with_retry("GET", url, headers=_jira_headers())
    if r is None:
        return None

    if r.status_code == 404:
        logger.warning("Jira ticket %s not found", ticket_key)
        return None

    if r.status_code >= 400:
        logger.warning("Jira API error %d for %s: %s", r.status_code, ticket_key, r.text[:200])
        return None

    return r.json()


def adf_to_text(node: dict | str | list | None, depth: int = 0) -> str:
    """
    Convert Atlassian Document Format (ADF) to plain text.
    Walks the content[] tree recursively.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(adf_to_text(item, depth) for item in node)
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type", "")

    # Text leaf
    if node_type == "text":
        return node.get("text", "")

    # Container nodes
    children = node.get("content", [])
    parts = [adf_to_text(child, depth + 1) for child in children]

    if node_type == "paragraph":
        return " ".join(p for p in parts if p) + "\n"
    elif node_type in ("bulletList", "orderedList"):
        return "\n".join(p for p in parts if p)
    elif node_type == "listItem":
        prefix = "  " * depth + "- "
        text = " ".join(p for p in parts if p)
        return f"{prefix}{text}"
    elif node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        text = " ".join(p for p in parts if p)
        return f"{'#' * level} {text}\n"
    elif node_type == "codeBlock":
        text = "\n".join(p for p in parts if p)
        return f"```\n{text}\n```\n"
    elif node_type == "table":
        return "\n".join(p for p in parts if p) + "\n"
    elif node_type in ("tableRow", "tableHeader", "tableCell"):
        return " | ".join(p for p in parts if p)
    elif node_type == "inlineCard":
        url = node.get("attrs", {}).get("url", "")
        return url if url else " ".join(p for p in parts if p)
    else:
        # Unknown node type — just concatenate children
        return " ".join(p for p in parts if p)


def extract_figma_urls(text: str) -> list[dict[str, str]]:
    """Extract Figma URLs from text, returning file_key and optional node_id."""
    results = []
    for match in FIGMA_URL_PATTERN.finditer(text or ""):
        file_key = match.group(2)
        node_id_raw = match.group(3)
        node_id = node_id_raw.replace("-", ":").replace("%3A", ":") if node_id_raw else ""
        results.append({
            "url": match.group(0),
            "file_key": file_key,
            "node_id": node_id,
        })
    return results


def get_issue_context(ticket_key: str) -> dict:
    """
    Fetch and parse a Jira issue into structured context.
    Returns a dict with: key, summary, type, epic, status, description, acceptance_criteria, figma_urls.
    Never crashes — returns partial data on failure.
    """
    result = {
        "key": ticket_key,
        "summary": "",
        "type": "",
        "epic": "",
        "status": "",
        "description": "",
        "acceptance_criteria": [],
        "figma_urls": [],
        "open_bugs": [],
    }

    issue = get_issue(ticket_key)
    if not issue:
        return result

    fields = issue.get("fields", {})
    result["summary"] = fields.get("summary", "")
    result["type"] = fields.get("issuetype", {}).get("name", "")
    result["status"] = fields.get("status", {}).get("name", "")

    # Epic link — try customfield_10014 or parent.key
    epic = fields.get("customfield_10014") or fields.get("parent", {}).get("key", "")
    result["epic"] = epic if isinstance(epic, str) else ""

    # Description (ADF → text)
    raw_desc = fields.get("description")
    desc_text = adf_to_text(raw_desc) if raw_desc else ""
    result["description"] = desc_text[:2000]

    # Extract Figma URLs from description
    result["figma_urls"] = extract_figma_urls(desc_text)

    # Acceptance criteria — try custom field or parse from description
    for key in ("customfield_10016", "customfield_10014", "customfield_10010"):
        raw = fields.get(key)
        if raw:
            if isinstance(raw, dict):
                ac = adf_to_text(raw)
            elif isinstance(raw, str):
                ac = raw
            else:
                continue
            if ac.strip():
                result["acceptance_criteria"] = [
                    line.strip().lstrip("- ").lstrip("* ")
                    for line in ac.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
                break

    return result


def get_open_bugs(project_key: str, feature_label: str) -> list[dict]:
    """
    Search for open bugs related to a feature via JQL.
    Returns list of {key, summary, status}.
    """
    if not config.jira_enabled():
        return []

    jql = (
        f'project = {project_key} AND issuetype = Bug '
        f'AND status != Done AND labels = "{feature_label}"'
    )
    url = _jira_url("/search")
    params = {"jql": jql, "maxResults": 10, "fields": "summary,status"}

    r = _request_with_retry("GET", url, headers=_jira_headers(), params=params)
    if r is None or r.status_code >= 400:
        logger.warning("Bug search failed for %s/%s", project_key, feature_label)
        return []

    data = r.json()
    bugs = []
    for issue in data.get("issues", []):
        bugs.append({
            "key": issue["key"],
            "summary": issue.get("fields", {}).get("summary", ""),
            "status": issue.get("fields", {}).get("status", {}).get("name", ""),
        })
    return bugs
