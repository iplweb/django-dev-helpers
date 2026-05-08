from __future__ import annotations

import logging
import sys
from pathlib import Path

from django_dev_helpers.project_root import resolve_project_root

logger = logging.getLogger(__name__)

# Default filenames; kept for backward compatibility. Prefer required_entries(cfg)
# when an actual config is available, since users may customise dotfile filenames
# via DJANGO_DEV_HELPERS["dotfiles"][..._filename].
ENTRIES = [
    ".dev_helpers_token",
    ".dev_helpers_port",
    ".dev_helpers_pg_host",
    ".dev_helpers_pg_port",
    ".dev_helpers_redis_host",
    ".dev_helpers_redis_port",
]


def required_entries(cfg) -> list[str]:
    df = cfg.dotfiles
    return [
        df.token_filename,
        df.port_filename,
        df.pg_host_filename,
        df.pg_port_filename,
        df.redis_host_filename,
        df.redis_port_filename,
    ]


def get_missing_entries(gitignore_content: str, cfg=None) -> list[str]:
    existing = {line.strip() for line in gitignore_content.splitlines()}
    entries = required_entries(cfg) if cfg is not None else ENTRIES
    return [entry for entry in entries if entry not in existing]


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

    missing = get_missing_entries(content, cfg)
    if not missing:
        return

    mode = cfg.gitignore.mode

    if mode == "off":
        return

    if mode == "warn":
        entries_str = "\n".join(f"  - {entry}" for entry in missing)
        logger.warning("django-dev-helpers: missing entries from .gitignore:\n%s", entries_str)
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
        sys.exit(f"Error: the following entries are missing from .gitignore:\n{entries_str}")
