import os
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings


def test_disabled_by_default():
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(DJANGO_DEV_HELPERS={}):
        os.environ.pop("DJANGO_DEV_HELPERS_ENABLED", None)
        cfg = DevHelpersConfig()
        assert not cfg.is_active()


def test_enabled_via_settings():
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True}):
        cfg = DevHelpersConfig()
        assert cfg.is_active()


def test_disabled_via_settings_override():
    from django_dev_helpers.conf import DevHelpersConfig

    os.environ["DJANGO_DEV_HELPERS_ENABLED"] = "1"
    with override_settings(DJANGO_DEV_HELPERS={"enabled": False}):
        cfg = DevHelpersConfig()
        assert not cfg.is_active()


def test_enabled_via_env():
    from django_dev_helpers.conf import DevHelpersConfig

    os.environ["DJANGO_DEV_HELPERS_ENABLED"] = "1"
    with override_settings(DJANGO_DEV_HELPERS={}):
        cfg = DevHelpersConfig()
        assert cfg.is_active()


def test_production_raises_when_serving():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.safety import assert_safe_to_activate

    os.environ["DJANGO_DEV_HELPERS_FORCE_SAFETY_CHECK"] = "1"
    with override_settings(
        DEBUG=False,
        DJANGO_DEV_HELPERS={"enabled": True},
    ):
        cfg = DevHelpersConfig()
        with pytest.raises(ImproperlyConfigured, match="cannot be enabled"):
            assert_safe_to_activate(cfg)


def test_non_serving_does_not_raise(monkeypatch):
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.safety import assert_safe_to_activate

    monkeypatch.setattr(sys, "argv", ["manage.py", "migrate"])
    os.environ.pop("DJANGO_DEV_HELPERS_FORCE_SAFETY_CHECK", None)
    with override_settings(
        DEBUG=False,
        DJANGO_DEV_HELPERS={"enabled": True},
    ):
        cfg = DevHelpersConfig()
        assert_safe_to_activate(cfg)


def test_refuse_if_inactive_raises_404():
    from django.http import Http404

    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(DJANGO_DEV_HELPERS={}):
        os.environ.pop("DJANGO_DEV_HELPERS_ENABLED", None)
        cfg = DevHelpersConfig()
        with pytest.raises(Http404):
            cfg.refuse_if_inactive()
