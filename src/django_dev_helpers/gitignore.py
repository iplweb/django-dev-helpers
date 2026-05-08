from __future__ import annotations

import logging
import sys
from pathlib import Path

from django_dev_helpers.project_root import resolve_project_root

logger = logging.getLogger(__name__)

ENTRIES = [
    ".dev_helpers_token",
    ".dev_helpers_port",
    ".dev_helpers_pg_host",
    ".dev_helpers_pg_port",
    ".dev_helpers_redis_host",
    ".dev_helpers_redis_port",
]


def get_missing_entries(gitignore_content: str) -> list[str]:
    existing = {line.strip() for line in gitignore_content.splitlines()}
    return [entry for entry in ENTRIES if entry not in existing]


def get_gitignore_path(cfg) -> Path:
    if cfg.gitignore.path:
        return Path(cfg.gitignore.path).resolve()
    return resolve_project_root(cfg) / ".gitignore"


def check_gitignore(cfg):
    project_root = resolve_project_root(cfg)
    if not (project_root / ".git").exists():
        return

    gitignore_path = get_gitignore_path(cfg)

    content = gitignore_path.read_text() if gitignore_path.exists() else ""

    missing = get_missing_entries(content)
    if not missing:
        return

    mode = cfg.gitignore.mode

    if mode == "off":
        return

    if mode == "warn":
        entries_str = "\n".join(f"  - {entry}" for entry in missing)
        logger.warning(
            "django-dev-helpers: missing entries from .gitignore:\n%s", entries_str
        )
        return

    if mode == "auto-add":
        header = "# django-dev-helpers"
        lines = [header, *missing]
        with open(gitignore_path, "a") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines) + "\n")
        return

    if mode == "error":
        entries_str = "\n".join(f"  - {entry}" for entry in missing)
        sys.exit(
            f"Error: the following entries are missing from .gitignore:\n{entries_str}"
        )
