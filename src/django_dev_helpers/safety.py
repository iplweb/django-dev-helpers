import os
import sys
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_NON_SERVING_COMMANDS = {
    "migrate", "makemigrations", "showmigrations", "sqlmigrate",
    "collectstatic", "compilemessages", "makemessages",
    "test", "check", "diffsettings",
    "shell", "dbshell",
    "createsuperuser", "changepassword",
    "dumpdata", "loaddata", "flush", "inspectdb",
    "dev_helpers_doctor", "dev_helpers_print_help",
    "dev_helpers_check_gitignore",
    "help", "version",
}


def _is_serving(cfg):
    if os.environ.get("DJANGO_DEV_HELPERS_FORCE_SAFETY_CHECK") == "1":
        return True
    if len(sys.argv) < 2:
        return True
    cmd = sys.argv[1]
    non_serving = set(_NON_SERVING_COMMANDS)
    extra = getattr(cfg, "safety", None)
    if extra is not None:
        extra_commands = getattr(extra, "non_serving_commands", None)
        if extra_commands is not None:
            non_serving.update(extra_commands)
    return cmd not in non_serving


def assert_safe_to_activate(cfg):
    if not _is_serving(cfg):
        return
    if not settings.DEBUG:
        raise ImproperlyConfigured(
            "django-dev-helpers cannot be enabled when settings.DEBUG=False "
            "and serving HTTP. This package exposes an autologin backdoor and "
            "is not safe for production. To use in dev: set DEBUG=True. To "
            "disable: remove DJANGO_DEV_HELPERS_ENABLED env var or set "
            "DJANGO_DEV_HELPERS['enabled'] = False."
        )


def emit_sanity_warnings(cfg):
    _localhost_hosts = {"localhost", "127.0.0.1", "*"}
    non_localhost = [h for h in settings.ALLOWED_HOSTS if h not in _localhost_hosts]
    if non_localhost:
        warnings.warn(
            f"django-dev-helpers: ALLOWED_HOSTS contains non-localhost entries: "
            f"{non_localhost}. Ensure this is not a production deployment.",
            RuntimeWarning,
            stacklevel=2,
        )
    secret = settings.SECRET_KEY
    if len(secret) >= 50 and not secret.startswith("django-insecure-"):
        warnings.warn(
            "django-dev-helpers: SECRET_KEY looks like a production secret "
            "(length >= 50, no 'django-insecure-' prefix). Ensure this is a "
            "dev environment.",
            RuntimeWarning,
            stacklevel=2,
        )
