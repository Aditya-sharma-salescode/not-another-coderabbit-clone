"""GitHub REST API client — fetch PR data, post comments, manage review markers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from reviewer import config

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REVIEW_MARKER = "<!-- AI-REVIEWER-v1 -->"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_repo(repo_slug: str | None = None) -> tuple[str, str]:
    slug = repo_slug or config.GITHUB_REPO
    if "/" not in slug:
        raise ValueError(f"GITHUB_REPO must be 'owner/repo', got: {slug!r}")
    owner, repo = slug.split("/", 1)
    return owner, repo


def get_pr(pr_number: int, repo_slug: str | None = None) -> dict[str, Any]:
    """Fetch PR metadata."""
    owner, repo = _parse_repo(repo_slug)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    with httpx.Client(timeout=30) as client:
        r = client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()


def get_pr_diff(pr_number: int, repo_slug: str | None = None) -> str:
    """Fetch the unified diff for a PR."""
    owner, repo = _parse_repo(repo_slug)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v3.diff"
    with httpx.Client(timeout=60) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        return r.text


def post_pr_comment(
    pr_number: int,
    body: str,
    repo_slug: str | None = None,
) -> dict[str, Any]:
    """Post an issue comment on a PR (not a review comment)."""
    owner, repo = _parse_repo(repo_slug)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    payload = {"body": f"{REVIEW_MARKER}\n{body}"}
    with httpx.Client(timeout=30) as client:
        r = client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        logger.info("Posted review comment on PR #%d", pr_number)
        return r.json()


def delete_old_review_comments(
    pr_number: int,
    marker: str = REVIEW_MARKER,
    repo_slug: str | None = None,
) -> int:
    """Delete previous AI review comments identified by marker. Returns count deleted."""
    owner, repo = _parse_repo(repo_slug)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    deleted = 0

    with httpx.Client(timeout=30) as client:
        page = 1
        while True:
            r = client.get(url, headers=_headers(), params={"per_page": 100, "page": page})
            r.raise_for_status()
            comments = r.json()
            if not comments:
                break

            for comment in comments:
                body = comment.get("body", "")
                if marker in body:
                    del_url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/comments/{comment['id']}"
                    dr = client.delete(del_url, headers=_headers())
                    if dr.status_code in (200, 204):
                        deleted += 1
                        logger.info("Deleted old review comment %d", comment["id"])

            if len(comments) < 100:
                break
            page += 1

    return deleted


def get_pr_files(pr_number: int, repo_slug: str | None = None) -> list[dict]:
    """Fetch list of changed files for a PR."""
    owner, repo = _parse_repo(repo_slug)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    files: list[dict] = []
    with httpx.Client(timeout=30) as client:
        page = 1
        while True:
            r = client.get(url, headers=_headers(), params={"per_page": 100, "page": page})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return files
