import logging
import os
import sys

from django.apps import AppConfig

# Sentinel env vars that survive Django runserver's autoreload (which uses
# os.execv on the same process — env is preserved, module state is not).
# Set after each one-shot side effect to avoid retriggering on reload.
_BROWSER_SENTINEL = "DEV_HELPERS_BROWSER_OPENED"
_HELP_SENTINEL = "DEV_HELPERS_HELP_PRINTED"

_AUTOLOGIN_MIDDLEWARE = "django_dev_helpers.middleware.AutologinMiddleware"

logger = logging.getLogger(__name__)


def install_autologin_middleware_if_enabled(cfg) -> None:
    """Append ``AutologinMiddleware`` to ``settings.MIDDLEWARE`` if the
    user hasn't already added it.

    Lets the autologin endpoint work in projects that haven't wired
    ``*autologin_urlpatterns()`` into their ``urls.py``. Gated by the
    ``autologin.middleware_autoinstall`` config flag (default True).

    The entry is appended at the end so every preceding middleware
    (``SessionMiddleware``, ``AuthenticationMiddleware``, and especially
    ``MessageMiddleware``) gets to set up the request state that the
    autologin view depends on -- in particular, ``request._messages``,
    which the view writes to when ``autologin.flash_message`` is
    configured. ``settings.MIDDLEWARE`` can be a list or tuple; we
    normalize to a list before mutating.
    """
    if not cfg.autologin.enabled:
        return
    if not cfg.autologin.middleware_autoinstall:
        return

    from django.conf import settings

    raw = getattr(settings, "MIDDLEWARE", None) or []
    middleware = list(raw)
    if _AUTOLOGIN_MIDDLEWARE in middleware:
        return

    middleware.append(_AUTOLOGIN_MIDDLEWARE)
    settings.MIDDLEWARE = middleware
    logger.debug("django-dev-helpers: auto-installed %s", _AUTOLOGIN_MIDDLEWARE)


class DjangoDevHelpersConfig(AppConfig):
    name = "django_dev_helpers"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from .conf import get_config

        cfg = get_config()
        if not cfg.is_active():
            return

        from .safety import _is_serving, assert_safe_to_activate, emit_sanity_warnings

        assert_safe_to_activate(cfg)
        emit_sanity_warnings(cfg)

        if cfg.autologin.enabled:
            from .tokens import init_token

            init_token()

        is_autoreload_parent = os.environ.get("RUN_MAIN") != "true"
        if not _is_serving(cfg):
            return
        if is_autoreload_parent and "runserver" in sys.argv:
            return

        install_autologin_middleware_if_enabled(cfg)

        if cfg.dotfiles.enabled:
            from .dotfiles import register_cleanup, write_all_dotfiles

            write_all_dotfiles(cfg)
            register_cleanup(cfg)

        if cfg.gitignore.mode != "off":
            from .gitignore import check_gitignore

            check_gitignore(cfg)

        if cfg.agent_help.auto_print and os.environ.get(_HELP_SENTINEL) != "1":
            from .prompt import register_first_request_print

            register_first_request_print(cfg)
            os.environ[_HELP_SENTINEL] = "1"

        if cfg.browser_open.enabled and os.environ.get(_BROWSER_SENTINEL) != "1":
            from .browser import spawn_self_probe_thread

            spawn_self_probe_thread(cfg)
            os.environ[_BROWSER_SENTINEL] = "1"
