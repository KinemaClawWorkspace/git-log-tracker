"""Configure global git template for automatic hook installation.

Usage:
    uv run python ~/.commit-logs/setup_global.py          # Enable global mode
    uv run python ~/.commit-logs/setup_global.py --off     # Disable global mode
"""

import argparse
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = Path.home() / ".git-templates"
MARKER_BEGIN = "# >>> git-commit-index >>>"
MARKER_END = "# <<< git-commit-index <<<"
HOOK_CONTENT = f"""#!/bin/sh
{MARKER_BEGIN}
uv run python "$HOME/.commit-logs/hook.py"
{MARKER_END}
"""


def enable():
    hooks_dir = TEMPLATE_DIR / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "post-commit"

    hook_file.write_text(HOOK_CONTENT, encoding="utf-8")
    print(f"Created template hook at {hook_file}")

    subprocess.run(
        ["git", "config", "--global", "init.templateDir", str(TEMPLATE_DIR)],
        check=True,
    )
    print(f"Set git global init.templateDir to {TEMPLATE_DIR}")
    print("New repos (git init / git clone) will automatically get the hook.")


def disable():
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


def main():
    parser = argparse.ArgumentParser(description="Configure global git template for commit logger")
    parser.add_argument("--off", action="store_true", help="Disable global mode")
    args = parser.parse_args()

    if args.off:
        disable()
    else:
        enable()


if __name__ == "__main__":
    main()
