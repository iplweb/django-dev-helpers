"""Tests for the ``DEV_HELPERS_ALLOWED_HOSTS`` env-var → ``settings.ALLOWED_HOSTS``
injection performed by :mod:`django_dev_helpers.allowed_hosts`."""

from __future__ import annotations

import pytest
from django.test import override_settings

from django_dev_helpers.allowed_hosts import ENV_VAR, inject_allowed_hosts


def test_no_env_var_is_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    with override_settings(ALLOWED_HOSTS=["localhost"]):
        from django.conf import settings

        before = list(settings.ALLOWED_HOSTS)
        added = inject_allowed_hosts()
        assert added == ()
        assert list(settings.ALLOWED_HOSTS) == before


def test_appends_new_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, "box.local,192.168.1.10")
    with override_settings(ALLOWED_HOSTS=["localhost"]):
        from django.conf import settings

        added = inject_allowed_hosts()
        assert set(added) == {"box.local", "192.168.1.10"}
        assert "localhost" in settings.ALLOWED_HOSTS
        assert "box.local" in settings.ALLOWED_HOSTS
        assert "192.168.1.10" in settings.ALLOWED_HOSTS


def test_skips_already_present_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, "localhost,box.local")
    with override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1"]):
        from django.conf import settings

        added = inject_allowed_hosts()
        assert added == ("box.local",)
        # No duplicate ``localhost``.
        assert settings.ALLOWED_HOSTS.count("localhost") == 1


def test_wildcard_in_settings_skips_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ALLOWED_HOSTS already accepts everything, our additions are
    redundant — leave the list untouched."""

    monkeypatch.setenv(ENV_VAR, "box.local,10.0.0.5")
    with override_settings(ALLOWED_HOSTS=["*"]):
        from django.conf import settings

        added = inject_allowed_hosts()
        assert added == ()
        assert list(settings.ALLOWED_HOSTS) == ["*"]


def test_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling twice — common when AppConfig.ready() runs again under
    runserver autoreload — must not duplicate entries."""

    monkeypatch.setenv(ENV_VAR, "box.local")
    with override_settings(ALLOWED_HOSTS=[]):
        from django.conf import settings

        first = inject_allowed_hosts()
        second = inject_allowed_hosts()
        assert first == ("box.local",)
        assert second == ()
        assert settings.ALLOWED_HOSTS.count("box.local") == 1


def test_strips_whitespace_and_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, " box.local , , 10.0.0.1 ")
    with override_settings(ALLOWED_HOSTS=[]):
        from django.conf import settings

        added = inject_allowed_hosts()
        assert set(added) == {"box.local", "10.0.0.1"}
        assert "box.local" in settings.ALLOWED_HOSTS


def test_empty_settings_initialises_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty ALLOWED_HOSTS should still work — we shouldn't crash on
    a list that's never been populated."""

    monkeypatch.setenv(ENV_VAR, "box.local")
    with override_settings(ALLOWED_HOSTS=[]):
        from django.conf import settings

        added = inject_allowed_hosts()
        assert added == ("box.local",)
        assert "box.local" in settings.ALLOWED_HOSTS
