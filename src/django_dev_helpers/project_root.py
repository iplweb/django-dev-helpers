import os
from pathlib import Path


def resolve_project_root(cfg) -> Path:
    if cfg.dotfiles.directory:
        return Path(cfg.dotfiles.directory).expanduser().resolve()
    env_value = os.environ.get("DEV_HELPERS_PROJECT_ROOT")
    if env_value:
        return Path(env_value).resolve()
    from django.conf import settings
    base_dir = Path(settings.BASE_DIR).resolve()
    markers = {"manage.py", "pyproject.toml", "runsite.toml", ".git"}
    for candidate in [base_dir, *base_dir.parents]:
        if any((candidate / m).exists() for m in markers):
            return candidate
    return base_dir
