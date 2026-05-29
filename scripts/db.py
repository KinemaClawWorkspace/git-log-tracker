"""Shared database utilities for git-commit-logger."""

import sqlite3
from pathlib import Path

DEFAULT_DB_DIR = Path.home() / ".commit-logs"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS commits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_hash     TEXT NOT NULL UNIQUE,
    short_hash      TEXT NOT NULL,
    author_name     TEXT NOT NULL,
    author_email    TEXT NOT NULL,
    author_ts       TEXT NOT NULL,
    committer_name  TEXT,
    committer_email TEXT,
    commit_subject  TEXT NOT NULL,
    commit_body     TEXT,
    branch          TEXT,
    repo_path       TEXT NOT NULL,
    repo_name       TEXT NOT NULL,
    parent_hashes   TEXT,
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_commit_hash ON commits(commit_hash);
CREATE INDEX IF NOT EXISTS idx_repo_path ON commits(repo_path);
CREATE INDEX IF NOT EXISTS idx_author_email ON commits(author_email);
CREATE INDEX IF NOT EXISTS idx_recorded_at ON commits(recorded_at);
"""


def get_db_path(config_path: Path | None = None) -> Path:
    if config_path is None:
        return DEFAULT_DB_PATH
    return config_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def read_config(config_path: Path | None = None) -> dict:
    if config_path is None:
        config_path = DEFAULT_DB_DIR / "config.toml"
    if not config_path.exists():
        return {"hooks": {"exclude": []}, "database": {"path": "index.db"}}
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(config_path, "rb") as f:
        return tomllib.load(f)
