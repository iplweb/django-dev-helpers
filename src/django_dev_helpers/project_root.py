import os
from pathlib import Path

# Strong markers unambiguously identify a run-site project root. They take
# precedence over generic markers because src/-layout projects have
# manage.py one level below the actual project root (where runsite.toml /
# .run-site-config live).
_RUN_SITE_MARKERS = ("runsite.toml", ".run-site-config")
_GENERIC_MARKERS = ("manage.py", "pyproject.toml", ".git")


def resolve_project_root(cfg) -> Path:
    if cfg.dotfiles.directory:
        return Path(cfg.dotfiles.directory).expanduser().resolve()
    env_value = os.environ.get("DEV_HELPERS_PROJECT_ROOT")
    if env_value:
        return Path(env_value).resolve()
    from django.conf import settings

    base_dir = Path(settings.BASE_DIR).resolve()

    for candidate in [base_dir, *base_dir.parents]:
        if any((candidate / m).exists() for m in _RUN_SITE_MARKERS):
            return candidate

    for candidate in [base_dir, *base_dir.parents]:
        if any((candidate / m).exists() for m in _GENERIC_MARKERS):
            return candidate
    return base_dir
