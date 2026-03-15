"""GitHub REST API client."""

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {settings.github_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def get_pr_detail(owner: str, repo: str, pull_number: int) -> dict[str, Any]:
    """Fetch PR metadata: title, body, head SHA, branch name."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json()


async def get_pr_files(owner: str, repo: str, pull_number: int) -> list[dict]:
    """
    Fetch list of changed files with their diff patches.
    Handles pagination (GitHub caps at 30 per page, max 300 files).
    """
    files: list[dict] = []
    page = 1
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/files"
            r = await client.get(url, headers=HEADERS, params={"per_page": 100, "page": page})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return files


async def post_review(
    owner: str,
    repo: str,
    pull_number: int,
    commit_id: str,
    body: str,
    comments: list[dict],
    event: str = "COMMENT",
) -> dict:
    """
    Post a PR review with optional inline comments.

    `event` options: "APPROVE", "REQUEST_CHANGES", "COMMENT"
    Each comment dict: {"path": str, "line": int, "side": "RIGHT"|"LEFT", "body": str}
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
    payload: dict[str, Any] = {
        "commit_id": commit_id,
        "body": body,
        "event": event,
        "comments": comments,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=HEADERS, json=payload)
        if r.status_code not in (200, 201):
            logger.error("GitHub review POST failed %s: %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()


async def set_commit_status(
    owner: str,
    repo: str,
    sha: str,
    state: str,
    description: str,
    context: str = "automated-pr-reviewer/review",
) -> dict:
    """
    Set a commit status check.

    `state`: "success" | "failure" | "pending" | "error"
    Use a fixed `context` string so branch protection rules can target it.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "description": description[:140],  # GitHub caps at 140 chars
        "context": context,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()
