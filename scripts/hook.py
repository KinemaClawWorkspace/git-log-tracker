"""Post-commit hook entry point for git-commit-logger.

Called by .git/hooks/post-commit after each successful commit.
Records commit metadata into SQLite index.
"""

import fnmatch
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, read_config, DEFAULT_DB_DIR


def get_repo_path() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout.strip()


def is_excluded(repo_path: str, config: dict) -> bool:
    excludes = config.get("hooks", {}).get("exclude", [])
    normalized = repo_path.replace("\\", "/")
    for pattern in excludes:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def get_commit_info(repo_path: str | None = None) -> dict:
    fmt = (
        "%H%n"      # full hash
        "%h%n"      # short hash
        "%an%n"     # author name
        "%ae%n"     # author email
        "%aI%n"     # author date ISO 8601
        "%cn%n"     # committer name
        "%ce%n"     # committer email
        "%s%n"      # subject
        "%b%n"      # body
        "%P%n"      # parent hashes
        "%D"        # ref names
    )
    cwd = repo_path if repo_path else None
    result = subprocess.run(
        ["git", "log", "-1", f"--format={fmt}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd,
    )
    lines = result.stdout.strip().split("\n")
    while len(lines) < 11:
        lines.append("")

    branch = None
    ref_names = lines[10] if len(lines) > 10 else ""
    for ref in ref_names.split(","):
        ref = ref.strip()
        if ref.startswith("HEAD -> "):
            branch = ref[len("HEAD -> "):]
            break

    body = lines[8] if len(lines) > 8 else ""
    parent_hashes = lines[9] if len(lines) > 9 else ""

    return {
        "commit_hash": lines[0],
        "short_hash": lines[1],
        "author_name": lines[2],
        "author_email": lines[3],
        "author_ts": lines[4],
        "committer_name": lines[5] or None,
        "committer_email": lines[6] or None,
        "commit_subject": lines[7],
        "commit_body": body or None,
        "branch": branch,
        "parent_hashes": parent_hashes or None,
    }


def main():
    try:
        config = read_config()
        repo_path = get_repo_path()
        if is_excluded(repo_path, config):
            return

        info = get_commit_info()
        repo_name = Path(repo_path).name

        db_path_setting = config.get("database", {}).get("path", "index.db")
        if Path(db_path_setting).is_absolute():
            db_path = Path(db_path_setting)
        else:
            db_path = DEFAULT_DB_DIR / db_path_setting

        conn = get_connection(db_path)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO commits (
                    commit_hash, short_hash, author_name, author_email, author_ts,
                    committer_name, committer_email, commit_subject, commit_body,
                    branch, repo_path, repo_name, parent_hashes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info["commit_hash"], info["short_hash"],
                info["author_name"], info["author_email"], info["author_ts"],
                info["committer_name"], info["committer_email"],
                info["commit_subject"], info["commit_body"],
                info["branch"], repo_path, repo_name, info["parent_hashes"],
            ))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[git-commit-logger] hook error: {e}", file=sys.stderr)
    # Always exit 0 — never block the commit


if __name__ == "__main__":
    main()
