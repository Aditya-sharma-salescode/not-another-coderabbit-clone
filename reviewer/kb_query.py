"""
Knowledge Base query engine — natural language queries against the registry.

Claude is given 11 tools covering registry + live Jira. It calls them in a loop
until it has enough information to answer, then returns a formatted text response.

Usage:
    from reviewer.kb_query import ask
    answer = ask("who updated order_checkout for cokearg_sfa?")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

import anthropic

from reviewer import config

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ITERATIONS = 10

SYSTEM_PROMPT = """\
You are a code intelligence assistant for the channelkart-flutter codebase.
You have access to a feature registry containing 150 features, 35 LOBs, Jira history, \
and git file history.

Answer questions about features, LOBs, code authors, Jira history, and change patterns.
Use the available tools to look up accurate data — never guess or hallucinate.
Be concise and direct. Format tables in markdown when listing multiple items.
If a feature or LOB is not found, say so clearly rather than returning empty results."""

TOOLS = [
    {
        "name": "list_features",
        "description": "List all feature names in the registry.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_feature",
        "description": (
            "Get the full registry record for a feature, including jira_history, "
            "git_file_history, lob_context, and related_features."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "description": "Feature name, e.g. 'order_checkout', 'sfa_attendance', 'ck_payment_dashboard'",
                }
            },
            "required": ["feature_name"],
        },
    },
    {
        "name": "search_feature_by_path",
        "description": "Find which feature owns a given file path using longest-prefix matching.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g. 'lib/features/cart/model/cart.dart'",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "list_lobs",
        "description": "List all LOB (Line of Business) names in the registry.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_lob",
        "description": "Get full configuration for a LOB including override pages and feature overrides.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lob_name": {
                    "type": "string",
                    "description": "LOB name, e.g. 'cokearg_sfa', 'SFA_Generic', 'unnati'",
                }
            },
            "required": ["lob_name"],
        },
    },
    {
        "name": "get_lob_overrides_for_feature",
        "description": (
            "Get all LOBs that have custom behavior (override pages, custom tests) for a given feature."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "description": "Feature name to check overrides for",
                }
            },
            "required": ["feature_name"],
        },
    },
    {
        "name": "who_changed",
        "description": (
            "Get the authors and change dates for files in a feature, "
            "optionally filtered to files relevant to a specific LOB."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "description": "Feature name",
                },
                "lob_name": {
                    "type": "string",
                    "description": "Optional LOB name to filter to LOB-specific context",
                },
            },
            "required": ["feature_name"],
        },
    },
    {
        "name": "get_jira_ticket",
        "description": "Fetch a Jira ticket by key (live API call). Returns summary, AC, status, epic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "Jira ticket key, e.g. 'CSLC-235', 'COCA-850'",
                }
            },
            "required": ["ticket_key"],
        },
    },
    {
        "name": "search_jira",
        "description": "Run a JQL query against Jira (live API call). Returns matching issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": (
                        "JQL query string, e.g. "
                        "'project = COCA AND issuetype = Bug AND status != Done AND labels = \"cart\"'"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["jql"],
        },
    },
    {
        "name": "get_recent_changes",
        "description": "Get files changed in the last N days for a feature, sorted by recency.",
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "description": "Feature name",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 90)",
                    "default": 90,
                },
            },
            "required": ["feature_name"],
        },
    },
    {
        "name": "get_sentinel_info",
        "description": "Get all sentinel paths and their impact descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_tool(name: str, args: dict, registry_path: str) -> str:
    """
    Dispatch a tool call to the appropriate function.
    Always returns a JSON string (Claude expects string tool results).
    """
    import reviewer.config as cfg
    cfg.REGISTRY_PATH = registry_path

    try:
        if name == "list_features":
            return _tool_list_features()
        elif name == "get_feature":
            return _tool_get_feature(args["feature_name"])
        elif name == "search_feature_by_path":
            return _tool_search_feature_by_path(args["file_path"])
        elif name == "list_lobs":
            return _tool_list_lobs()
        elif name == "get_lob":
            return _tool_get_lob(args["lob_name"])
        elif name == "get_lob_overrides_for_feature":
            return _tool_get_lob_overrides_for_feature(args["feature_name"])
        elif name == "who_changed":
            return _tool_who_changed(args["feature_name"], args.get("lob_name"))
        elif name == "get_jira_ticket":
            return _tool_get_jira_ticket(args["ticket_key"])
        elif name == "search_jira":
            return _tool_search_jira(args["jql"], args.get("max_results", 10))
        elif name == "get_recent_changes":
            return _tool_get_recent_changes(args["feature_name"], args.get("days", 90))
        elif name == "get_sentinel_info":
            return _tool_get_sentinel_info()
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------

def _tool_list_features() -> str:
    from reviewer.registry import list_all_features
    features = list_all_features()
    return json.dumps({"features": features, "count": len(features)})


def _tool_get_feature(feature_name: str) -> str:
    from reviewer.registry import load_feature
    data = load_feature(feature_name)
    if data is None:
        return json.dumps({"error": f"Feature '{feature_name}' not found in registry"})
    return json.dumps(data, default=str)


def _tool_search_feature_by_path(file_path: str) -> str:
    from reviewer.lob_mapper import map_path_to_feature, load_index
    index = load_index()
    feature = map_path_to_feature(file_path, index)
    sentinel = index.get("sentinel_paths", {}).get(feature or "", "")
    return json.dumps({
        "file_path": file_path,
        "feature": feature,
        "is_sentinel": bool(sentinel),
        "sentinel_warning": sentinel,
    })


def _tool_list_lobs() -> str:
    from reviewer.lob_mapper import load_lob_index
    lob_index = load_lob_index()
    lobs = list(lob_index.get("lobs", {}).keys())
    return json.dumps({"lobs": lobs, "count": len(lobs)})


def _tool_get_lob(lob_name: str) -> str:
    from reviewer.lob_mapper import load_lob_index
    lob_index = load_lob_index()
    lob_data = lob_index.get("lobs", {}).get(lob_name)
    if lob_data is None:
        # Try case-insensitive match
        for key, val in lob_index.get("lobs", {}).items():
            if key.lower() == lob_name.lower():
                lob_data = val
                break
    if lob_data is None:
        return json.dumps({"error": f"LOB '{lob_name}' not found"})
    return json.dumps(lob_data, default=str)


def _tool_get_lob_overrides_for_feature(feature_name: str) -> str:
    from reviewer.lob_mapper import load_lob_index, get_affected_lobs
    lob_index = load_lob_index()
    affected = get_affected_lobs(feature_name, lob_index)
    return json.dumps({
        "feature": feature_name,
        "lobs_with_overrides": affected,
        "count": len(affected),
    })


def _tool_who_changed(feature_name: str, lob_name: str | None) -> str:
    from reviewer.registry import load_feature
    data = load_feature(feature_name)
    if data is None:
        return json.dumps({"error": f"Feature '{feature_name}' not found"})

    git_history = data.get("git_file_history", {})

    # If LOB specified, filter to files mentioned in that LOB's overrides
    if lob_name and data.get("lob_context", {}).get(lob_name):
        lob_ctx = data["lob_context"][lob_name]
        override_pages = lob_ctx.get("override_pages", [])
        if override_pages:
            git_history = {
                path: info for path, info in git_history.items()
                if any(page.lower() in path.lower() for page in override_pages)
            }

    # Aggregate: all unique authors + most recent modification
    all_authors: set[str] = set()
    most_recent = ""
    file_summary = []

    for path, info in sorted(git_history.items(), key=lambda x: x[1].get("last_modified", ""), reverse=True):
        authors = info.get("authors", [])
        all_authors.update(authors)
        last_mod = info.get("last_modified", "")
        if last_mod > most_recent:
            most_recent = last_mod
        file_summary.append({
            "file": path,
            "last_modified": last_mod,
            "commit_count": info.get("commit_count", 0),
            "authors": authors,
        })

    return json.dumps({
        "feature": feature_name,
        "lob_filter": lob_name,
        "all_authors": sorted(all_authors),
        "most_recent_change": most_recent,
        "files": file_summary[:20],  # cap output
    })


def _tool_get_jira_ticket(ticket_key: str) -> str:
    if not config.jira_enabled():
        return json.dumps({"error": "Jira not configured (JIRA_BASE_URL/EMAIL/API_TOKEN missing)"})
    from reviewer.jira_client import get_issue_context
    ctx = get_issue_context(ticket_key.upper())
    return json.dumps(ctx, default=str)


def _tool_search_jira(jql: str, max_results: int = 10) -> str:
    if not config.jira_enabled():
        return json.dumps({"error": "Jira not configured"})
    from reviewer.jira_client import _request_with_retry, _jira_headers, _jira_url
    r = _request_with_retry(
        "GET",
        _jira_url("/search"),
        headers=_jira_headers(),
        params={"jql": jql, "maxResults": max_results, "fields": "summary,status,issuetype,priority,assignee"},
    )
    if r is None or r.status_code >= 400:
        return json.dumps({"error": f"Jira search failed: {r.status_code if r else 'no response'}"})

    data = r.json()
    issues = []
    for issue in data.get("issues", []):
        f = issue.get("fields", {})
        issues.append({
            "key": issue["key"],
            "summary": f.get("summary", ""),
            "status": f.get("status", {}).get("name", ""),
            "type": f.get("issuetype", {}).get("name", ""),
            "priority": f.get("priority", {}).get("name", ""),
        })
    return json.dumps({"jql": jql, "total": data.get("total", 0), "issues": issues})


def _tool_get_recent_changes(feature_name: str, days: int = 90) -> str:
    from reviewer.registry import load_feature
    data = load_feature(feature_name)
    if data is None:
        return json.dumps({"error": f"Feature '{feature_name}' not found"})

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    git_history = data.get("git_file_history", {})

    recent = []
    for path, info in git_history.items():
        last_mod = info.get("last_modified", "")
        if last_mod >= cutoff:
            recent.append({
                "file": path,
                "last_modified": last_mod,
                "commit_count": info.get("commit_count", 0),
                "authors": info.get("authors", []),
            })

    recent.sort(key=lambda x: x["last_modified"], reverse=True)

    return json.dumps({
        "feature": feature_name,
        "days": days,
        "cutoff": cutoff,
        "files_changed": recent,
        "count": len(recent),
    })


def _tool_get_sentinel_info() -> str:
    from reviewer.lob_mapper import load_index
    index = load_index()
    sentinel_paths = index.get("sentinel_paths", {})
    path_to_feature = index.get("path_to_feature", {})

    # Find actual file paths that map to sentinel features
    sentinels = []
    for file_path, feature_name in path_to_feature.items():
        if feature_name in sentinel_paths:
            sentinels.append({
                "file_path": file_path,
                "feature_key": feature_name,
                "impact": sentinel_paths[feature_name],
            })

    return json.dumps({"sentinel_paths": sentinels, "count": len(sentinels)})


# ---------------------------------------------------------------------------
# Main ask() function
# ---------------------------------------------------------------------------

def ask(question: str, registry_path: str = "registry", use_live: bool = True) -> str:
    """
    Answer a natural language question using registry data and optionally live APIs.

    Args:
        question: The user's question in plain English
        registry_path: Path to the registry directory
        use_live: If False, Jira/GitHub tool calls return a "disabled" message

    Returns:
        Formatted text answer from Claude
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Build tool list — optionally strip live tools
    tools = TOOLS
    if not use_live:
        live_tool_names = {"get_jira_ticket", "search_jira"}
        tools = [t for t in TOOLS if t["name"] not in live_tool_names]

    messages: list[dict] = [{"role": "user", "content": question}]

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        # If Claude is done (no tool calls), return the text
        if response.stop_reason == "end_turn":
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts)

        # Process tool calls
        tool_results = []
        has_tool_use = False

        for block in response.content:
            if block.type == "tool_use":
                has_tool_use = True
                logger.info("Tool call: %s(%s)", block.name, json.dumps(block.input)[:100])
                result = execute_tool(block.name, block.input, registry_path)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if not has_tool_use:
            # No tool calls and stop_reason wasn't end_turn — extract any text
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts) if text_parts else "(no response)"

        # Feed tool results back
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return f"(query exceeded {MAX_TOOL_ITERATIONS} tool iterations — try a more specific question)"
