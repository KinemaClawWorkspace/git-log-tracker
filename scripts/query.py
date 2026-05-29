"""Query CLI for git-commit-logger.

Subcommands:
    find <hash>              Find commit by hash (supports prefix)
    list                     List recent commits
    stats                    Show statistics
    record [repo]            Manually record latest commit from a repo
    delete <hash>            Delete a commit record
    update <hash> <field> <value>  Update a field

Usage:
    uv run python ~/.commit-logs/query.py find abc1234
    uv run python ~/.commit-logs/query.py list -n 50 --repo task-tracker
    uv run python ~/.commit-logs/query.py stats
    uv run python ~/.commit-logs/query.py record .
    uv run python ~/.commit-logs/query.py delete abc1234
    uv run python ~/.commit-logs/query.py update abc1234 branch main
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, DEFAULT_DB_DIR

EDITABLE_FIELDS = {"branch", "commit_subject", "commit_body", "repo_path", "repo_name"}


def cmd_find(args):
    conn = get_connection()
    try:
        if len(args.hash) >= 40:
            row = conn.execute(
                "SELECT * FROM commits WHERE commit_hash = ?", (args.hash,)
            ).fetchone()
        else:
            rows = conn.execute(
                "SELECT * FROM commits WHERE commit_hash LIKE ?",
                (args.hash + "%",),
            ).fetchall()
            if len(rows) == 0:
                print(f"Commit not found: {args.hash}")
                return
            if len(rows) > 1:
                print(f"Multiple commits match prefix '{args.hash}':")
                for r in rows:
                    print(f"  {r['short_hash']}  {r['commit_subject'][:60]}")
                return
            row = rows[0]

        print(f"commit  {row['commit_hash']}")
        print(f"author  {row['author_name']} <{row['author_email']}>")
        print(f"date    {row['author_ts']}")
        print(f"repo    {row['repo_path']}")
        print(f"branch  {row['branch'] or '(detached)'}")
        print(f"subject {row['commit_subject']}")
        if row['commit_body']:
            print(f"body    {row['commit_body'][:200]}")
        if row['parent_hashes']:
            print(f"parents {row['parent_hashes']}")
    finally:
        conn.close()


def cmd_list(args):
    conn = get_connection()
    try:
        sql = "SELECT * FROM commits WHERE 1=1"
        params = []

        if args.repo:
            sql += " AND (repo_name = ? OR repo_path LIKE ?)"
            params.extend([args.repo, f"%{args.repo}%"])
        if args.author:
            sql += " AND author_email = ?"
            params.append(args.author)
        if args.since:
            sql += " AND author_ts >= ?"
            params.append(args.since)
        if args.until:
            sql += " AND author_ts <= ?"
            params.append(args.until)
        if args.branch:
            sql += " AND branch = ?"
            params.append(args.branch)

        sql += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(args.n)

        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print("No commits found.")
            return

        # Format as table
        fmt = "{:<10} {:<20} {:<15} {:<20} {}"
        print(fmt.format("HASH", "DATE", "AUTHOR", "REPO", "SUBJECT"))
        print("-" * 100)
        for r in rows:
            date = r['author_ts'][:19].replace("T", " ")[:16] if r['author_ts'] else ""
            author = r['author_name'][:15]
            subject = (r['commit_subject'] or "")[:40]
            print(fmt.format(
                r['short_hash'], date, author, r['repo_name'], subject
            ))
    finally:
        conn.close()


def cmd_stats(args):
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
        repos = conn.execute(
            "SELECT repo_name, COUNT(*) as cnt FROM commits GROUP BY repo_name ORDER BY cnt DESC"
        ).fetchall()
        authors = conn.execute(
            "SELECT author_name, COUNT(*) as cnt FROM commits GROUP BY author_email ORDER BY cnt DESC"
        ).fetchall()
        recent = conn.execute(
            "SELECT MIN(author_ts) as earliest, MAX(author_ts) as latest FROM commits"
        ).fetchone()

        print(f"Total commits: {total}")
        if recent['earliest']:
            print(f"Date range: {recent['earliest'][:10]} ~ {recent['latest'][:10]}")
        print(f"\nBy repo ({len(repos)}):")
        for r in repos[:10]:
            print(f"  {r['repo_name']:<30} {r['cnt']}")
        print(f"\nBy author ({len(authors)}):")
        for a in authors[:10]:
            print(f"  {a['author_name']:<30} {a['cnt']}")
    finally:
        conn.close()


def cmd_record(args):
    """Manually record the latest commit from a repo."""
    import fnmatch
    import hook as hook_mod
    from db import read_config

    if args.repo:
        repo_path = str(Path(args.repo).resolve())
    else:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            print("Error: not in a git repository", file=sys.stderr)
            return
        repo_path = result.stdout.strip()

    config = read_config()
    if hook_mod.is_excluded(repo_path, config):
        print(f"Repo excluded: {repo_path}")
        return

    info = hook_mod.get_commit_info(repo_path)
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
        print(f"Recorded: {info['short_hash']} {info['commit_subject'][:60]}")
    finally:
        conn.close()


def cmd_delete(args):
    conn = get_connection()
    try:
        if len(args.hash) >= 40:
            cur = conn.execute("DELETE FROM commits WHERE commit_hash = ?", (args.hash,))
        else:
            cur = conn.execute("DELETE FROM commits WHERE commit_hash LIKE ?", (args.hash + "%",))
        conn.commit()
        if cur.rowcount:
            print(f"Deleted {cur.rowcount} commit(s)")
        else:
            print(f"Commit not found: {args.hash}")
    finally:
        conn.close()


def cmd_update(args):
    field = args.field
    if field not in EDITABLE_FIELDS:
        print(f"Field '{field}' is not editable. Editable fields: {', '.join(sorted(EDITABLE_FIELDS))}")
        return

    conn = get_connection()
    try:
        if len(args.hash) >= 40:
            cur = conn.execute(
                f"UPDATE commits SET {field} = ? WHERE commit_hash = ?",
                (args.value, args.hash),
            )
        else:
            cur = conn.execute(
                f"UPDATE commits SET {field} = ? WHERE commit_hash LIKE ?",
                (args.value, args.hash + "%"),
            )
        conn.commit()
        if cur.rowcount:
            print(f"Updated {field} for {args.hash}")
        else:
            print(f"Commit not found: {args.hash}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Git Commit Logger Query CLI")
    sub = parser.add_subparsers(dest="command")

    # find
    p_find = sub.add_parser("find", help="Find commit by hash")
    p_find.add_argument("hash", help="Commit hash (full or prefix)")

    # list
    p_list = sub.add_parser("list", help="List recent commits")
    p_list.add_argument("-n", type=int, default=20, help="Number of results (default: 20)")
    p_list.add_argument("--repo", help="Filter by repo name")
    p_list.add_argument("--author", help="Filter by author email")
    p_list.add_argument("--since", help="Filter since date (ISO 8601)")
    p_list.add_argument("--until", help="Filter until date (ISO 8601)")
    p_list.add_argument("--branch", help="Filter by branch name")

    # stats
    sub.add_parser("stats", help="Show commit statistics")

    # record
    p_record = sub.add_parser("record", help="Manually record latest commit from a repo")
    p_record.add_argument("repo", nargs="?", help="Path to git repo (default: current)")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a commit record")
    p_delete.add_argument("hash", help="Commit hash (full or prefix)")

    # update
    p_update = sub.add_parser("update", help="Update a commit record field")
    p_update.add_argument("hash", help="Commit hash (full or prefix)")
    p_update.add_argument("field", help=f"Field to update ({', '.join(sorted(EDITABLE_FIELDS))})")
    p_update.add_argument("value", help="New value")

    args = parser.parse_args()

    if args.command == "find":
        cmd_find(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "update":
        cmd_update(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
