import os

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings


def test_unknown_top_level_key_raises():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "no_such_section": {}}),
        pytest.raises(ImproperlyConfigured, match="unknown top-level keys"),
    ):
        DevHelpersConfig()


def test_invalid_gitignore_mode_raises():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "gitignore": {"mode": "WARN"}}),
        pytest.raises(ImproperlyConfigured, match=r"gitignore.*mode"),
    ):
        DevHelpersConfig()


def test_invalid_lookup_source_raises():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "magic"}}),
        pytest.raises(ImproperlyConfigured, match=r"lookup.*source"),
    ):
        DevHelpersConfig()


def test_extra_cookies_must_be_list_of_dicts():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "autologin": {"extra_cookies": "not-a-list"}}),
        pytest.raises(ImproperlyConfigured, match="extra_cookies"),
    ):
        DevHelpersConfig()

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "autologin": {"extra_cookies": ["not-a-dict"]}}),
        pytest.raises(ImproperlyConfigured, match="extra_cookies"),
    ):
        DevHelpersConfig()


def test_allowed_hosts_must_be_list():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "autologin": {"allowed_hosts": "ngrok.io"}}),
        pytest.raises(ImproperlyConfigured, match="allowed_hosts"),
    ):
        DevHelpersConfig()


def test_callable_must_be_string_or_none():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"callable": 42}}),
        pytest.raises(ImproperlyConfigured, match="callable"),
    ):
        DevHelpersConfig()


def test_autologin_username_env_var_overrides_default():
    from django_dev_helpers.conf import DevHelpersConfig

    os.environ["DEV_HELPERS_AUTOLOGIN_USERNAME"] = "from-env"
    try:
        with override_settings(DJANGO_DEV_HELPERS={"enabled": True}):
            cfg = DevHelpersConfig()
            assert cfg.autologin.user_lookup_value == "from-env"
    finally:
        os.environ.pop("DEV_HELPERS_AUTOLOGIN_USERNAME", None)


def test_explicit_user_lookup_value_beats_env():
    from django_dev_helpers.conf import DevHelpersConfig

    os.environ["DEV_HELPERS_AUTOLOGIN_USERNAME"] = "from-env"
    try:
        with override_settings(
            DJANGO_DEV_HELPERS={
                "enabled": True,
                "autologin": {"user_lookup_value": "explicit"},
            }
        ):
            cfg = DevHelpersConfig()
            assert cfg.autologin.user_lookup_value == "explicit"
    finally:
        os.environ.pop("DEV_HELPERS_AUTOLOGIN_USERNAME", None)


def test_safety_non_serving_commands_extension():
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "safety": {"non_serving_commands": ["my_custom_cmd"]},
        }
    ):
        cfg = DevHelpersConfig()
        assert "my_custom_cmd" in cfg.safety.non_serving_commands


def test_settings_must_be_dict():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS=["not", "a", "dict"]),
        pytest.raises(ImproperlyConfigured, match="must be a dict"),
    ):
        DevHelpersConfig()
