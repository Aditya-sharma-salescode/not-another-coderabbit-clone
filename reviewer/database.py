"""SQLite database layer for the PR reviewer registry and review history."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from reviewer import config

logger = logging.getLogger(__name__)

DB_FILENAME = "pr_reviewer.db"


def _db_path() -> str:
    return os.path.join(config.REGISTRY_PATH, DB_FILENAME)


@contextmanager
def get_db():
    """Yield a sqlite3 connection with row_factory set to Row."""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Database initialized at %s", _db_path())


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS features (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    namespace   TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT UNIQUE NOT NULL,
    display_name TEXT DEFAULT '',
    config       TEXT DEFAULT '{}',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lob_feature_overrides (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    lob_id         INTEGER NOT NULL REFERENCES lobs(id),
    feature_id     INTEGER NOT NULL REFERENCES features(id),
    override_pages TEXT DEFAULT '[]',
    notes          TEXT DEFAULT '',
    UNIQUE(lob_id, feature_id)
);

CREATE TABLE IF NOT EXISTS jira_tickets (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_key           TEXT UNIQUE NOT NULL,
    summary              TEXT DEFAULT '',
    ticket_type          TEXT DEFAULT '',
    status               TEXT DEFAULT '',
    epic                 TEXT DEFAULT '',
    acceptance_criteria  TEXT DEFAULT '[]',
    figma_links          TEXT DEFAULT '[]',
    fetched_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_jira_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id  INTEGER NOT NULL REFERENCES features(id),
    ticket_id   INTEGER NOT NULL REFERENCES jira_tickets(id),
    branch      TEXT DEFAULT '',
    linked_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feature_id, ticket_id)
);

CREATE TABLE IF NOT EXISTS git_file_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id    INTEGER NOT NULL REFERENCES features(id),
    file_path     TEXT NOT NULL,
    last_modified DATE NOT NULL,
    commit_count  INTEGER DEFAULT 1,
    UNIQUE(feature_id, file_path)
);

CREATE TABLE IF NOT EXISTS file_authors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL REFERENCES git_file_history(id),
    author     TEXT NOT NULL,
    UNIQUE(history_id, author)
);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo            TEXT NOT NULL,
    pr_number       INTEGER NOT NULL,
    branch          TEXT DEFAULT '',
    jira_key        TEXT DEFAULT '',
    recommendation  TEXT DEFAULT '',
    issues_found    INTEGER DEFAULT 0,
    critical_count  INTEGER DEFAULT 0,
    review_text     TEXT DEFAULT '',
    prompt_tokens   INTEGER DEFAULT 0,
    model_used      TEXT DEFAULT 'claude-sonnet-4-6',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_features (
    review_id   INTEGER NOT NULL REFERENCES reviews(id),
    feature_id  INTEGER NOT NULL REFERENCES features(id),
    PRIMARY KEY(review_id, feature_id)
);

CREATE TABLE IF NOT EXISTS review_sentinel_warnings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    file_path TEXT NOT NULL,
    warning   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_config (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    repo              TEXT UNIQUE NOT NULL,
    stack             TEXT DEFAULT 'flutter',
    skip_patterns     TEXT DEFAULT '[]',
    jira_projects     TEXT DEFAULT '[]',
    custom_prompt     TEXT DEFAULT '',
    registry_enabled  INTEGER DEFAULT 1,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_features_name ON features(name);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_key ON jira_tickets(ticket_key);
CREATE INDEX IF NOT EXISTS idx_git_history_feature ON git_file_history(feature_id);
CREATE INDEX IF NOT EXISTS idx_git_history_modified ON git_file_history(last_modified);
CREATE INDEX IF NOT EXISTS idx_reviews_repo_pr ON reviews(repo, pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at);
CREATE INDEX IF NOT EXISTS idx_review_features_feature ON review_features(feature_id);
"""


# ---------------------------------------------------------------------------
# Migration: JSON files → SQLite
# ---------------------------------------------------------------------------

def migrate_from_json(registry_path: str | None = None) -> dict:
    """
    Read existing JSON registry files and insert into the database.
    Returns a summary dict with counts.
    """
    reg = registry_path or config.REGISTRY_PATH
    old_registry = config.REGISTRY_PATH
    config.REGISTRY_PATH = reg
    init_db()

    stats = {"features": 0, "lobs": 0, "overrides": 0, "jira_tickets": 0, "git_files": 0}

    with get_db() as conn:
        # --- Features ---
        features_dir = os.path.join(reg, "features")
        if os.path.isdir(features_dir):
            for fname in sorted(os.listdir(features_dir)):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(features_dir, fname)
                with open(fpath) as f:
                    data = json.load(f)

                name = data.get("feature_name", fname.removesuffix(".json"))
                source_paths = data.get("source_paths", [])
                source_path = source_paths[0] if source_paths else ""
                namespace = ""
                if "lib/sfa/features/" in source_path:
                    namespace = "lib/sfa/features/"
                elif "lib/channelKart/features/" in source_path:
                    namespace = "lib/channelKart/features/"
                elif "lib/features/" in source_path:
                    namespace = "lib/features/"

                conn.execute(
                    "INSERT OR IGNORE INTO features (name, namespace, source_path) VALUES (?, ?, ?)",
                    (name, namespace, source_path),
                )
                feat_id = conn.execute("SELECT id FROM features WHERE name = ?", (name,)).fetchone()["id"]
                stats["features"] += 1

                # Jira history
                for ticket in data.get("jira_history", []):
                    tk = ticket.get("ticket_key", "")
                    if not tk:
                        continue
                    conn.execute(
                        """INSERT OR IGNORE INTO jira_tickets
                           (ticket_key, summary, ticket_type, status, epic, acceptance_criteria, figma_links)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            tk,
                            ticket.get("summary", ""),
                            ticket.get("ticket_type", ""),
                            ticket.get("status", ""),
                            ticket.get("epic", ""),
                            json.dumps(ticket.get("acceptance_criteria", [])),
                            json.dumps(ticket.get("figma_links", [])),
                        ),
                    )
                    ticket_id = conn.execute(
                        "SELECT id FROM jira_tickets WHERE ticket_key = ?", (tk,)
                    ).fetchone()["id"]
                    conn.execute(
                        "INSERT OR IGNORE INTO feature_jira_history (feature_id, ticket_id, branch) VALUES (?, ?, ?)",
                        (feat_id, ticket_id, ticket.get("branch", "")),
                    )
                    stats["jira_tickets"] += 1

                # Git file history
                for file_path, info in data.get("git_file_history", {}).items():
                    conn.execute(
                        """INSERT OR IGNORE INTO git_file_history
                           (feature_id, file_path, last_modified, commit_count)
                           VALUES (?, ?, ?, ?)""",
                        (feat_id, file_path, info.get("last_modified", ""), info.get("commit_count", 1)),
                    )
                    hist_row = conn.execute(
                        "SELECT id FROM git_file_history WHERE feature_id = ? AND file_path = ?",
                        (feat_id, file_path),
                    ).fetchone()
                    if hist_row:
                        for author in info.get("authors", []):
                            conn.execute(
                                "INSERT OR IGNORE INTO file_authors (history_id, author) VALUES (?, ?)",
                                (hist_row["id"], author),
                            )
                    stats["git_files"] += 1

        # --- LOBs ---
        lob_path = os.path.join(reg, "lob_index.json")
        if os.path.exists(lob_path):
            with open(lob_path) as f:
                lob_index = json.load(f)

            for lob_name, lob_data in lob_index.get("lobs", {}).items():
                conn.execute(
                    "INSERT OR IGNORE INTO lobs (name, display_name, config) VALUES (?, ?, ?)",
                    (lob_name, lob_name, json.dumps({"enabled_features": lob_data.get("enabled_features", [])})),
                )
                lob_id = conn.execute("SELECT id FROM lobs WHERE name = ?", (lob_name,)).fetchone()["id"]
                stats["lobs"] += 1

                for feat_name, overrides in lob_data.get("overrides", {}).items():
                    feat_row = conn.execute("SELECT id FROM features WHERE name = ?", (feat_name,)).fetchone()
                    if feat_row:
                        conn.execute(
                            """INSERT OR IGNORE INTO lob_feature_overrides
                               (lob_id, feature_id, override_pages, notes)
                               VALUES (?, ?, ?, ?)""",
                            (
                                lob_id,
                                feat_row["id"],
                                json.dumps(overrides.get("override_pages", [])),
                                overrides.get("notes", ""),
                            ),
                        )
                        stats["overrides"] += 1

    config.REGISTRY_PATH = old_registry
    return stats


# ---------------------------------------------------------------------------
# Query helpers (used by the API)
# ---------------------------------------------------------------------------

def get_all_features() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, namespace, source_path, updated_at FROM features ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_feature_detail(feature_name: str) -> dict | None:
    with get_db() as conn:
        feat = conn.execute("SELECT * FROM features WHERE name = ?", (feature_name,)).fetchone()
        if not feat:
            return None

        feat_id = feat["id"]

        # Jira history
        jira = conn.execute(
            """SELECT j.ticket_key, j.summary, j.ticket_type, j.status, j.epic, fj.branch, fj.linked_at
               FROM feature_jira_history fj
               JOIN jira_tickets j ON j.id = fj.ticket_id
               WHERE fj.feature_id = ?
               ORDER BY fj.linked_at DESC""",
            (feat_id,),
        ).fetchall()

        # Git history
        git_files = conn.execute(
            """SELECT g.file_path, g.last_modified, g.commit_count,
                      GROUP_CONCAT(fa.author) as authors
               FROM git_file_history g
               LEFT JOIN file_authors fa ON fa.history_id = g.id
               WHERE g.feature_id = ?
               GROUP BY g.id
               ORDER BY g.last_modified DESC""",
            (feat_id,),
        ).fetchall()

        # LOB overrides
        overrides = conn.execute(
            """SELECT l.name as lob_name, lo.override_pages, lo.notes
               FROM lob_feature_overrides lo
               JOIN lobs l ON l.id = lo.lob_id
               WHERE lo.feature_id = ?""",
            (feat_id,),
        ).fetchall()

        return {
            **dict(feat),
            "jira_history": [dict(r) for r in jira],
            "git_file_history": [
                {**dict(r), "authors": (r["authors"] or "").split(",")} for r in git_files
            ],
            "lob_overrides": [
                {**dict(r), "override_pages": json.loads(r["override_pages"] or "[]")} for r in overrides
            ],
        }


def get_all_lobs() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, display_name FROM lobs ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_all_reviews(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT r.*, GROUP_CONCAT(f.name) as features
               FROM reviews r
               LEFT JOIN review_features rf ON rf.review_id = r.id
               LEFT JOIN features f ON f.id = rf.feature_id
               GROUP BY r.id
               ORDER BY r.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {**dict(r), "features": (r["features"] or "").split(",") if r["features"] else []}
            for r in rows
        ]


def save_review(
    repo: str,
    pr_number: int,
    branch: str,
    jira_key: str,
    recommendation: str,
    issues_found: int,
    critical_count: int,
    review_text: str,
    prompt_tokens: int,
    feature_names: list[str],
    sentinel_warnings: list[dict] | None = None,
) -> int:
    """Save a review to the database. Returns the review ID."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO reviews
               (repo, pr_number, branch, jira_key, recommendation,
                issues_found, critical_count, review_text, prompt_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (repo, pr_number, branch, jira_key, recommendation,
             issues_found, critical_count, review_text, prompt_tokens),
        )
        review_id = cur.lastrowid

        for fname in feature_names:
            feat = conn.execute("SELECT id FROM features WHERE name = ?", (fname,)).fetchone()
            if feat:
                conn.execute(
                    "INSERT OR IGNORE INTO review_features (review_id, feature_id) VALUES (?, ?)",
                    (review_id, feat["id"]),
                )

        if sentinel_warnings:
            for sw in sentinel_warnings:
                conn.execute(
                    "INSERT INTO review_sentinel_warnings (review_id, file_path, warning) VALUES (?, ?, ?)",
                    (review_id, sw.get("file_path", ""), sw.get("warning", "")),
                )

        return review_id


def get_dashboard_stats() -> dict:
    """Aggregate stats for the dashboard."""
    with get_db() as conn:
        total_features = conn.execute("SELECT COUNT(*) as c FROM features").fetchone()["c"]
        total_lobs = conn.execute("SELECT COUNT(*) as c FROM lobs").fetchone()["c"]
        total_reviews = conn.execute("SELECT COUNT(*) as c FROM reviews").fetchone()["c"]

        reviews_this_month = conn.execute(
            "SELECT COUNT(*) as c FROM reviews WHERE created_at > date('now', '-30 days')"
        ).fetchone()["c"]

        recommendations = conn.execute(
            """SELECT recommendation, COUNT(*) as c FROM reviews
               WHERE created_at > date('now', '-30 days')
               GROUP BY recommendation"""
        ).fetchall()

        top_features = conn.execute(
            """SELECT f.name, COUNT(rf.review_id) as review_count
               FROM features f
               JOIN review_features rf ON rf.feature_id = f.id
               GROUP BY f.id ORDER BY review_count DESC LIMIT 10"""
        ).fetchall()

        stale_features = conn.execute(
            """SELECT f.name, MAX(g.last_modified) as last_change
               FROM features f
               LEFT JOIN git_file_history g ON g.feature_id = f.id
               GROUP BY f.id
               HAVING last_change < date('now', '-90 days') OR last_change IS NULL
               ORDER BY last_change ASC
               LIMIT 10"""
        ).fetchall()

        recent_reviews = conn.execute(
            """SELECT r.id, r.repo, r.pr_number, r.branch, r.recommendation,
                      r.issues_found, r.critical_count, r.created_at,
                      GROUP_CONCAT(f.name) as features
               FROM reviews r
               LEFT JOIN review_features rf ON rf.review_id = r.id
               LEFT JOIN features f ON f.id = rf.feature_id
               GROUP BY r.id
               ORDER BY r.created_at DESC LIMIT 10"""
        ).fetchall()

        return {
            "total_features": total_features,
            "total_lobs": total_lobs,
            "total_reviews": total_reviews,
            "reviews_this_month": reviews_this_month,
            "recommendations": {r["recommendation"]: r["c"] for r in recommendations},
            "top_features": [dict(r) for r in top_features],
            "stale_features": [dict(r) for r in stale_features],
            "recent_reviews": [
                {**dict(r), "features": (r["features"] or "").split(",") if r["features"] else []}
                for r in recent_reviews
            ],
        }
