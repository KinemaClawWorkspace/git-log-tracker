"""Install/uninstall/status git post-commit hook for commit logging.

Usage:
    uv run python ~/.commit-logs/install.py <repo_path>
    uv run python ~/.commit-logs/install.py .
    uv run python ~/.commit-logs/install.py --uninstall <repo_path>
    uv run python ~/.commit-logs/install.py --status <repo_path>
"""

import argparse
import sys
from pathlib import Path

MARKER_BEGIN = "# >>> git-commit-index >>>"
MARKER_END = "# <<< git-commit-index <<<"
HOOK_LINES = """\
{begin}
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMIT_LOGGER_HOME="$(dirname "$HOOK_DIR")"
# Try multiple locations for the hook script
for loc in "$COMMIT_LOGGER_HOME/commit-logs" "$HOME/.commit-logs"; do
    if [ -f "$loc/hook.py" ]; then
        uv run python "$loc/hook.py"
        break
    fi
done
{end}""".format(begin=MARKER_BEGIN, end=MARKER_END)


def resolve_repo(path: str) -> Path:
    repo = Path(path).resolve()
    if not (repo / ".git").exists():
        print(f"Error: {repo} is not a git repository", file=sys.stderr)
        sys.exit(1)
    return repo


def find_deployed_hook_path() -> str:
    """Return the path to hook.py that should be called."""
    return "$HOME/.commit-logs/hook.py"


def get_hook_content() -> str:
    return f"""#!/bin/sh
{HOOK_LINES}
"""


def install(repo: Path):
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "post-commit"

    if hook_file.exists():
        content = hook_file.read_text(encoding="utf-8", errors="replace")
        if MARKER_BEGIN in content:
            print(f"Hook already installed in {repo}")
            return

        # Append our hook to existing file
        with open(hook_file, "a", encoding="utf-8") as f:
            f.write(f"\n{HOOK_LINES}\n")
        print(f"Hook appended to existing post-commit in {repo}")
    else:
        hook_file.write_text(get_hook_content(), encoding="utf-8")
        print(f"Hook created at {hook_file}")


def uninstall(repo: Path):
    hook_file = repo / ".git" / "hooks" / "post-commit"
    if not hook_file.exists():
        print(f"No post-commit hook found in {repo}")
        return

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if MARKER_BEGIN not in content:
        print(f"No git-commit-index hook found in {repo}")
        return

    # Remove our block
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


def status(repo: Path):
    hook_file = repo / ".git" / "hooks" / "post-commit"
    if not hook_file.exists():
        print(f"Status: not installed (no post-commit hook) [{repo}]")
        return

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if MARKER_BEGIN in content:
        print(f"Status: installed [{repo}]")
    else:
        print(f"Status: not installed (post-commit exists but no our marker) [{repo}]")


def main():
    parser = argparse.ArgumentParser(description="Manage git post-commit hook")
    parser.add_argument("repo", help="Path to git repository (use '.' for current)")
    parser.add_argument("--uninstall", action="store_true", help="Remove the hook")
    parser.add_argument("--status", action="store_true", help="Check hook status")
    args = parser.parse_args()

    repo = resolve_repo(args.repo)

    if args.status:
        status(repo)
    elif args.uninstall:
        uninstall(repo)
    else:
        install(repo)


if __name__ == "__main__":
    main()
