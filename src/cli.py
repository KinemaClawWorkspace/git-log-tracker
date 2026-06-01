"""CLI entry point for git-log-tracker.

Subcommands:
    install <repo>        Install hook to repo
    uninstall <repo>      Remove hook from repo
    status <repo>         Check hook status
    global                Configure global git template
    find <hash>           Find commit by hash
    list                  List recent commits
    stats                 Show statistics
    record <repo>         Manually record commit
    delete <hash>         Delete commit record
    hook                  Run hook logic (called by post-commit)
    reinstall             Reset and reinitialize data directory
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from __init__ import __version__
from config import (
    read_config, is_excluded_repo, ensure_config_exists,
    DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH,
    add_label, remove_label, paths_for_label, labels_for_path, read_labels,
)
from db import get_connection, get_schema_version, SCHEMA_VERSION, DEFAULT_DB_DIR, DEFAULT_DB_PATH
from hook import get_commit_info, record_commit

# Hook installation constants
MARKER_BEGIN = "# >>> git-log-tracker >>>"
MARKER_END = "# <<< git-log-tracker <<<"

EDITABLE_FIELDS = {"branch", "commit_subject", "commit_body", "repo_path", "repo_name"}

# Global template constants
TEMPLATE_DIR = Path.home() / ".git-templates"


# =============================================================================
# Hook management commands
# =============================================================================

def resolve_repo(path: str) -> Path:
    repo = Path(path).resolve()
    if not (repo / ".git").exists():
        print(f"Error: {repo} is not a git repository", file=sys.stderr)
        sys.exit(1)
    return repo


def get_hook_content() -> str:
    return f"""#!/bin/sh
{MARKER_BEGIN}
git-log-tracker hook
{MARKER_END}
"""


def cmd_install(args):
    """Install hook to specified repo."""
    repo = resolve_repo(args.repo)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "post-commit"

    hook_lines = f"""
{MARKER_BEGIN}
git-log-tracker hook
{MARKER_END}
"""

    if hook_file.exists():
        content = hook_file.read_text(encoding="utf-8", errors="replace")
        if MARKER_BEGIN in content:
            print(f"Hook already installed in {repo}")
            return

        with open(hook_file, "a", encoding="utf-8") as f:
            f.write(hook_lines)
        print(f"Hook appended to existing post-commit in {repo}")
    else:
        hook_file.write_text(get_hook_content(), encoding="utf-8")
        print(f"Hook created at {hook_file}")


def cmd_uninstall(args):
    """Remove hook from specified repo."""
    repo = resolve_repo(args.repo)
    hook_file = repo / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        print(f"No post-commit hook found in {repo}")
        return

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if MARKER_BEGIN not in content:
        print(f"No git-log-tracker hook found in {repo}")
        return

    lines = content.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if MARKER_BEGIN in line:
            skip = True
            continue
        if MARKER_END in line:
            skip = False
            continue
        if not skip:
            new_lines.append(line)

    result = "\n".join(new_lines).strip()
    if result:
        hook_file.write_text(result + "\n", encoding="utf-8")
        print(f"Hook removed from {repo}, existing hooks preserved")
    else:
        hook_file.unlink()
        print(f"Hook file removed (was only our hook)")


def cmd_status(args):
    """Check hook status in specified repo."""
    repo = resolve_repo(args.repo)
    hook_file = repo / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        print(f"Status: not installed (no post-commit hook) [{repo}]")
        return

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if MARKER_BEGIN in content:
        print(f"Status: installed [{repo}]")
    else:
        print(f"Status: not installed (post-commit exists but no marker) [{repo}]")


# =============================================================================
# Global template commands
# =============================================================================

def get_global_hook_content() -> str:
    return f"""#!/bin/sh
{MARKER_BEGIN}
git-log-tracker hook
{MARKER_END}
"""


def cmd_global(args):
    """Configure global git template for automatic hook installation."""
    if args.off:
        result = subprocess.run(
            ["git", "config", "--global", "--get", "init.templateDir"],
            capture_output=True, text=True,
        )
        if result.stdout.strip() == str(TEMPLATE_DIR):
            subprocess.run(["git", "config", "--global", "--unset", "init.templateDir"])
            print("Unset git global init.templateDir")
        else:
            print("init.templateDir is not set to our template dir, skipping unset")

        hook_file = TEMPLATE_DIR / "hooks" / "post-commit"
        if hook_file.exists():
            hook_file.unlink()
            print(f"Removed {hook_file}")
    else:
        hooks_dir = TEMPLATE_DIR / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_file = hooks_dir / "post-commit"

        hook_file.write_text(get_global_hook_content(), encoding="utf-8")
        print(f"Created template hook at {hook_file}")

        subprocess.run(
            ["git", "config", "--global", "init.templateDir", str(TEMPLATE_DIR)],
            check=True,
        )
        print(f"Set git global init.templateDir to {TEMPLATE_DIR}")
        print("New repos (git init / git clone) will automatically get the hook.")


# =============================================================================
# Query commands
# =============================================================================

def _path_variants(paths) -> list[str]:
    """Expand normalized paths into both slash variants for SQL matching."""
    variants = []
    for p in paths:
        fwd = p.replace("\\", "/")
        back = p.replace("/", "\\")
        for v in (fwd, back):
            if v not in variants:
                variants.append(v)
    return variants


def _label_where(label):
    """Build (where_fragment, params) for a label filter.

    Returns (None, None) if the label matches no repos.
    Returns ("", []) if no label requested.
    """
    if not label:
        return "", []
    paths = paths_for_label(label)
    if not paths:
        return None, None
    variants = _path_variants(paths)
    placeholders = ",".join("?" * len(variants))
    return f" AND repo_path IN ({placeholders})", variants


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
        if getattr(args, "label", None):
            frag, lparams = _label_where(args.label)
            if frag is None:
                print(f"No repos with label '{args.label}'")
                return
            sql += frag
            params.extend(lparams)

        sql += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(args.n)

        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print("No commits found.")
            return

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
    where, wparams = "", []
    if getattr(args, "label", None):
        frag, lparams = _label_where(args.label)
        if frag is None:
            print(f"No repos with label '{args.label}'")
            return
        # frag begins with " AND "; convert to a WHERE clause
        where = " WHERE " + frag[len(" AND "):]
        wparams = lparams

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM commits{where}", wparams
        ).fetchone()[0]
        repos = conn.execute(
            f"SELECT repo_name, COUNT(*) as cnt FROM commits{where} "
            "GROUP BY repo_name ORDER BY cnt DESC", wparams
        ).fetchall()
        authors = conn.execute(
            f"SELECT author_name, COUNT(*) as cnt FROM commits{where} "
            "GROUP BY author_email ORDER BY cnt DESC", wparams
        ).fetchall()
        recent = conn.execute(
            f"SELECT MIN(author_ts) as earliest, MAX(author_ts) as latest FROM commits{where}",
            wparams
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


def cmd_label(args):
    """Manage repo-level labels."""
    if args.action == "list":
        if args.repo:
            labels = labels_for_path(args.repo)
            repo = str(Path(args.repo).resolve()).replace("\\", "/")
            if labels:
                print(f"{repo} -> {', '.join(labels)}")
            else:
                print(f"{repo} has no labels")
        else:
            data = read_labels()
            if not data:
                print("No labels defined.")
                return
            for path, labels in data.items():
                print(f"{path} -> {', '.join(labels)}")
        return

    if not args.repo:
        print("Error: repo path required", file=sys.stderr)
        return

    if args.action == "add":
        if not args.labels:
            print("Error: at least one label required", file=sys.stderr)
            return
        repo = Path(args.repo).resolve()
        if not (repo / ".git").exists():
            print(f"Warning: {repo} is not a git repository", file=sys.stderr)
        for label in args.labels:
            add_label(str(repo), label)
        print(f"Labeled {str(repo).replace(chr(92), '/')} with: {', '.join(args.labels)}")
        print(f"Current labels: {', '.join(labels_for_path(str(repo)))}")

    elif args.action == "rm":
        if not args.labels:
            print("Error: a label to remove is required", file=sys.stderr)
            return
        repo = Path(args.repo).resolve()
        for label in args.labels:
            if remove_label(str(repo), label):
                print(f"Removed label '{label}' from {str(repo).replace(chr(92), '/')}")
            else:
                print(f"Repo has no label '{label}'")


def cmd_record(args):
    """Manually record the latest commit from a repo."""
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
    if is_excluded_repo(repo_path, config):
        print(f"Repo excluded: {repo_path}")
        return

    success = record_commit(repo_path)
    if success:
        info = get_commit_info(repo_path)
        print(f"Recorded: {info['short_hash']} {info['commit_subject'][:60]}")


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


def cmd_hook(args):
    """Run hook logic (called by post-commit hook)."""
    record_commit()
    # Always exit 0


def cmd_setup(args):
    """Initialize config directory and database if not exist."""
    config_path = ensure_config_exists()
    print(f"Config: {config_path}")

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.close()
    print(f"Database: {DEFAULT_DB_PATH}")
    print("Setup complete.")


def cmd_reinstall(args):
    """Reset data directory and reinitialize."""
    if DEFAULT_CONFIG_DIR.exists():
        if args.keep_config:
            # Only delete database
            if DEFAULT_DB_PATH.exists():
                DEFAULT_DB_PATH.unlink()
                print(f"Deleted database: {DEFAULT_DB_PATH}")
        else:
            shutil.rmtree(DEFAULT_CONFIG_DIR)
            print(f"Deleted data directory: {DEFAULT_CONFIG_DIR}")

    # Reinitialize
    config_path = ensure_config_exists()
    print(f"Created config: {config_path}")

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.close()
    print(f"Created database: {DEFAULT_DB_PATH}")
    print("Reinstall complete.")


def cmd_migrate(args):
    """Run database migrations."""
    current = get_schema_version(DEFAULT_DB_PATH)
    print(f"Current schema version: {current}")
    print(f"Latest version: {SCHEMA_VERSION}")

    if current >= SCHEMA_VERSION:
        print("Database is up to date.")
        return

    print("Running migrations...")
    conn = get_connection()
    conn.close()
    print(f"Migrated: {current} -> {SCHEMA_VERSION}")


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="git-log-tracker",
        description="Git post-commit hook + SQLite commit index CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    # setup
    p_setup = sub.add_parser("setup", help="Initialize config and database")

    # reinstall
    p_reinstall = sub.add_parser("reinstall", help="Reset and reinitialize")
    p_reinstall.add_argument("--keep-config", action="store_true", help="Keep config, only reset database")

    # migrate
    sub.add_parser("migrate", help="Run database migrations")

    # install
    p_install = sub.add_parser("install", help="Install hook to a repo")
    p_install.add_argument("repo", help="Path to git repo (use '.' for current)")

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove hook from a repo")
    p_uninstall.add_argument("repo", help="Path to git repo")

    # status
    p_status = sub.add_parser("status", help="Check hook status in a repo")
    p_status.add_argument("repo", help="Path to git repo")

    # global
    p_global = sub.add_parser("global", help="Configure global git template")
    p_global.add_argument("--off", action="store_true", help="Disable global mode")

    # find
    p_find = sub.add_parser("find", help="Find commit by hash")
    p_find.add_argument("hash", help="Commit hash (full or prefix)")

    # list
    p_list = sub.add_parser("list", help="List recent commits")
    p_list.add_argument("-n", type=int, default=20, help="Number of results")
    p_list.add_argument("--repo", help="Filter by repo name")
    p_list.add_argument("--author", help="Filter by author email")
    p_list.add_argument("--since", help="Filter since date (ISO 8601)")
    p_list.add_argument("--until", help="Filter until date (ISO 8601)")
    p_list.add_argument("--branch", help="Filter by branch name")
    p_list.add_argument("--label", help="Filter by repo label")

    # stats
    p_stats = sub.add_parser("stats", help="Show commit statistics")
    p_stats.add_argument("--label", help="Filter by repo label")

    # label
    p_label = sub.add_parser("label", help="Manage repo-level labels")
    p_label.add_argument("action", choices=["add", "rm", "list"])
    p_label.add_argument("repo", nargs="?", help="Path to git repo")
    p_label.add_argument("labels", nargs="*", help="Label name(s)")

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

    # hook
    sub.add_parser("hook", help="Run hook logic (called by post-commit)")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "reinstall":
        cmd_reinstall(args)
    elif args.command == "migrate":
        cmd_migrate(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "global":
        cmd_global(args)
    elif args.command == "find":
        cmd_find(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "label":
        cmd_label(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "hook":
        cmd_hook(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()