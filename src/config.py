"""Configuration management for git-log-tracker."""

import fnmatch
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".commit-logs"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


def read_config(config_path: Path | None = None) -> dict:
    """Read configuration from TOML file."""
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return {"hooks": {"exclude": []}, "database": {"path": "index.db"}}

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def is_excluded_repo(repo_path: str, config: dict) -> bool:
    """Check if repo_path matches any exclude pattern."""
    excludes = config.get("hooks", {}).get("exclude", [])
    normalized = repo_path.replace("\\", "/")
    for pattern in excludes:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def get_default_config_content() -> str:
    """Return default config.toml content."""
    return """\
[hooks]
# Exclude patterns (fnmatch syntax)
# Supports exact repo paths and wildcard prefixes
exclude = [
    "/tmp/*",
]

[database]
# Relative to ~/.commit-logs/ or absolute path
path = "index.db"
"""


def ensure_config_exists() -> Path:
    """Ensure config directory and file exist, return config path."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.write_text(get_default_config_content(), encoding="utf-8")
    return DEFAULT_CONFIG_PATH