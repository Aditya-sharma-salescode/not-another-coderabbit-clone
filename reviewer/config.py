"""Load and validate environment variables from .env file."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def validate_required() -> None:
    """Validate required env vars are set. Called by CLI before running."""
    missing = []
    for name in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN"):
        if not os.getenv(name, "").strip():
            missing.append(name)
    if missing:
        print(f"ERROR: Required environment variables not set: {', '.join(missing)}", file=sys.stderr)
        print(f"  Copy .env.example to .env and fill in your secrets.", file=sys.stderr)
        sys.exit(1)


# --- Required (read at import time, validated lazily by validate_required()) ---
ANTHROPIC_API_KEY: str = _optional("ANTHROPIC_API_KEY")
GITHUB_TOKEN: str = _optional("GITHUB_TOKEN")

# --- Jira (optional — reviewer still works without it) ---
JIRA_BASE_URL: str = _optional("JIRA_BASE_URL")
JIRA_EMAIL: str = _optional("JIRA_EMAIL")
JIRA_API_TOKEN: str = _optional("JIRA_API_TOKEN")

# --- Figma (optional) ---
FIGMA_ACCESS_TOKEN: str = _optional("FIGMA_ACCESS_TOKEN")

# --- Registry ---
REGISTRY_PATH: str = _optional("REGISTRY_PATH", "registry")

# --- GitHub context (set by CI or CLI) ---
PR_NUMBER: str = _optional("PR_NUMBER")
BASE_SHA: str = _optional("BASE_SHA")
HEAD_SHA: str = _optional("HEAD_SHA")
BRANCH_NAME: str = _optional("BRANCH_NAME")
GITHUB_REPO: str = _optional("GITHUB_REPO")  # owner/repo

# --- Tokens for registry write-back ---
REVIEWER_REPO_TOKEN: str = _optional("REVIEWER_REPO_TOKEN")
REGISTRY_WRITE_TOKEN: str = _optional("REGISTRY_WRITE_TOKEN")

# --- Known Jira project keys ---
JIRA_PROJECTS: list[str] = ["CSLC", "COCA", "CT", "MYB2B", "PS", "UI"]


def jira_enabled() -> bool:
    return bool(JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN)


def figma_enabled() -> bool:
    return bool(FIGMA_ACCESS_TOKEN)
