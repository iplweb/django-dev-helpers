"""Tests that exercise AppConfig.ready() side-effect orchestration.

ready() runs once at Django startup, but for tests we re-invoke it
explicitly with controlled environments to verify token init, sentinel
gating, and the order of side effects.
"""

import os
import sys
from unittest import mock

import pytest
from django.test import override_settings


@pytest.fixture
def runserver_argv(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])


@pytest.fixture
def autoreload_child(monkeypatch):
    monkeypatch.setenv("RUN_MAIN", "true")


def _clear_sentinels():
    for key in (
        "DEV_HELPERS_BROWSER_OPENED",
        "DEV_HELPERS_HELP_PRINTED",
        "DEV_HELPERS_AUTOLOGIN_TOKEN",
    ):
        os.environ.pop(key, None)


def test_token_initialised_during_ready(runserver_argv, autoreload_child, tmp_path):
    _clear_sentinels()
    with override_settings(
        DEBUG=True,
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"enabled": False},
            "agent_help": {"auto_print": False},
            "browser_open": {"enabled": False},
            "gitignore": {"mode": "off"},
        },
    ):
        from django_dev_helpers.apps import DjangoDevHelpersConfig
        from django_dev_helpers.conf import reset_config

        reset_config()
        config = DjangoDevHelpersConfig.create("django_dev_helpers")
        config.ready()
        assert os.environ.get("DEV_HELPERS_AUTOLOGIN_TOKEN")


def test_browser_sentinel_gates_second_ready(runserver_argv, autoreload_child, tmp_path):
    _clear_sentinels()
    with override_settings(
        DEBUG=True,
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"enabled": False},
            "agent_help": {"auto_print": False},
            "browser_open": {"enabled": True, "probe_timeout_seconds": 0.1},
            "gitignore": {"mode": "off"},
        },
    ):
        from django_dev_helpers.apps import DjangoDevHelpersConfig
        from django_dev_helpers.conf import reset_config

        reset_config()
        config = DjangoDevHelpersConfig.create("django_dev_helpers")

        with mock.patch("django_dev_helpers.browser.spawn_self_probe_thread") as spawn:
            config.ready()
            assert spawn.call_count == 1
            assert os.environ.get("DEV_HELPERS_BROWSER_OPENED") == "1"

            config.ready()
            assert spawn.call_count == 1


def test_help_print_sentinel_gates_second_ready(runserver_argv, autoreload_child, tmp_path):
    _clear_sentinels()
    with override_settings(
        DEBUG=True,
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"enabled": False},
            "agent_help": {"auto_print": True},
            "browser_open": {"enabled": False},
            "gitignore": {"mode": "off"},
        },
    ):
        from django_dev_helpers.apps import DjangoDevHelpersConfig
        from django_dev_helpers.conf import reset_config

        reset_config()
        config = DjangoDevHelpersConfig.create("django_dev_helpers")

        with mock.patch("django_dev_helpers.prompt.register_first_request_print") as reg:
            config.ready()
            assert reg.call_count == 1
            assert os.environ.get("DEV_HELPERS_HELP_PRINTED") == "1"

            config.ready()
            assert reg.call_count == 1


def test_inactive_skips_all_side_effects(monkeypatch, tmp_path):
    _clear_sentinels()
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])
    monkeypatch.delenv("DJANGO_DEV_HELPERS_ENABLED", raising=False)
    with override_settings(DJANGO_DEV_HELPERS={"enabled": False}):
        from django_dev_helpers.apps import DjangoDevHelpersConfig
        from django_dev_helpers.conf import reset_config

        reset_config()
        config = DjangoDevHelpersConfig.create("django_dev_helpers")

        with (
            mock.patch("django_dev_helpers.tokens.init_token") as token,
            mock.patch("django_dev_helpers.browser.spawn_self_probe_thread") as spawn,
        ):
            config.ready()
            assert token.call_count == 0
            assert spawn.call_count == 0


def test_autoreload_parent_skips_side_effects(monkeypatch, tmp_path):
    _clear_sentinels()
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])
    monkeypatch.delenv("RUN_MAIN", raising=False)
    with override_settings(
        DEBUG=True,
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"enabled": True},
            "agent_help": {"auto_print": True},
            "browser_open": {"enabled": True},
            "gitignore": {"mode": "off"},
        },
    ):
        from django_dev_helpers.apps import DjangoDevHelpersConfig
        from django_dev_helpers.conf import reset_config

        reset_config()
        config = DjangoDevHelpersConfig.create("django_dev_helpers")

        with (
            mock.patch("django_dev_helpers.dotfiles.write_all_dotfiles") as write,
            mock.patch("django_dev_helpers.browser.spawn_self_probe_thread") as spawn,
        ):
            config.ready()
            # Parent watcher: token still init'd (so child inherits) but
            # no dotfile writes, no browser open.
            assert os.environ.get("DEV_HELPERS_AUTOLOGIN_TOKEN")
            assert write.call_count == 0
            assert spawn.call_count == 0


def test_install_live_reload_middleware_appends_when_enabled():
    from django_dev_helpers.apps import install_live_reload_middleware_if_enabled
    from django_dev_helpers.conf import get_config, reset_config

    mw = "django_dev_helpers.middleware.LiveReloadMiddleware"
    with override_settings(MIDDLEWARE=[], DJANGO_DEV_HELPERS={"enabled": True}):
        reset_config()
        install_live_reload_middleware_if_enabled(get_config())
        from django.conf import settings

        assert mw in settings.MIDDLEWARE


def test_install_live_reload_middleware_skipped_when_disabled():
    from django_dev_helpers.apps import install_live_reload_middleware_if_enabled
    from django_dev_helpers.conf import get_config, reset_config

    mw = "django_dev_helpers.middleware.LiveReloadMiddleware"
    with override_settings(MIDDLEWARE=[], DJANGO_DEV_HELPERS={"enabled": True, "live_reload": {"enabled": False}}):
        reset_config()
        install_live_reload_middleware_if_enabled(get_config())
        from django.conf import settings

        assert mw not in settings.MIDDLEWARE


def test_install_live_reload_middleware_idempotent():
    from django_dev_helpers.apps import install_live_reload_middleware_if_enabled
    from django_dev_helpers.conf import get_config, reset_config

    mw = "django_dev_helpers.middleware.LiveReloadMiddleware"
    with override_settings(MIDDLEWARE=[mw], DJANGO_DEV_HELPERS={"enabled": True}):
        reset_config()
        install_live_reload_middleware_if_enabled(get_config())
        from django.conf import settings

        assert settings.MIDDLEWARE.count(mw) == 1
