import os
from unittest.mock import patch

import pytest
from django.test import override_settings


@pytest.fixture
def cfg_for_prompt(tmp_path):
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(tmp_path)},
        }
    ):
        cfg = DevHelpersConfig()
        yield cfg


def test_default_template_renders(cfg_for_prompt, tmp_path):
    os.environ["DEV_HELPERS_PORT"] = "8000"
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = "test-token"
    from django_dev_helpers.prompt import render_template

    result = render_template(cfg_for_prompt)
    assert "http://localhost:8000" in result
    assert str(tmp_path / ".dev_helpers_token") in result
    assert "__autologin__/" in result
    os.environ.pop("DEV_HELPERS_PORT", None)
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_custom_template():
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "agent_help": {
                "template": "Custom: {host}:{port}",
            },
            "dotfiles": {"directory": str(tmp)},
        }
    ):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config

        reset_config()
        from django_dev_helpers.prompt import render_template

        os.environ["DEV_HELPERS_PORT"] = "9999"
        cfg = DevHelpersConfig()
        result = render_template(cfg)
        assert result == "Custom: localhost:9999"
        os.environ.pop("DEV_HELPERS_PORT", None)


def test_show_db_credentials_false():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.prompt import render_template

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "agent_help": {"show_db_credentials": False},
            "dotfiles": {"directory": "/tmp"},
        }
    ):
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        result = render_template(cfg)
        assert "<redacted>" in result
        assert "PGPASSWORD" not in result
        os.environ.pop("DEV_HELPERS_PORT", None)


def test_host_substitution():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.prompt import render_template

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": "/tmp"},
        }
    ):
        cfg = DevHelpersConfig()
        with patch("django_dev_helpers.dotfiles.discover_bind_host", return_value="0.0.0.0"):
            os.environ["DEV_HELPERS_PORT"] = "8000"
            result = render_template(cfg)
            assert "http://localhost:" in result
            assert "0.0.0.0" not in result
            os.environ.pop("DEV_HELPERS_PORT", None)
