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
    """``show_db_credentials = False`` redacts the Postgres user / password
    in the rendered banner. Requires a Postgres-backed setup — for SQLite
    projects there are no credentials to redact (the banner shows just
    the file path, which isn't treated as a secret)."""

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "agent_help": {"show_db_credentials": False},
            "dotfiles": {"directory": "/tmp"},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "127.0.0.1",
                "PORT": "5432",
                "NAME": "demo",
                "USER": "demo",
                "PASSWORD": "demo-pwd",
            },
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
        assert "<redacted>" in result
        assert "PGPASSWORD" not in result
        assert "demo-pwd" not in result


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


def test_sqlite_path_name_is_coerced_for_shlex(tmp_path):
    """SQLite projects ship ``DATABASES['default']['NAME']`` as a
    ``pathlib.Path`` (``BASE_DIR / "db.sqlite3"``). ``render_template``
    used to feed that straight into ``shlex.quote``, raising
    ``TypeError: expected string or bytes-like object``. Regression
    guard: a Path NAME must round-trip without exploding."""

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    db_path = tmp_path / "db.sqlite3"
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": db_path,
            },
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
        # The Path becomes a str, so it shows up in the rendered template
        # without raising. ``shlex.quote`` may wrap it in single quotes if
        # the path contains shell-special chars; either form is fine.
        assert str(db_path) in result


def _clear_dev_helpers_env() -> None:
    for key in (
        "DEV_HELPERS_DB_HOST",
        "DEV_HELPERS_DB_PORT",
        "DEV_HELPERS_DB_NAME",
        "DEV_HELPERS_DB_USER",
        "DEV_HELPERS_DB_PASSWORD",
        "DEV_HELPERS_REDIS_HOST",
        "DEV_HELPERS_REDIS_PORT",
    ):
        os.environ.pop(key, None)


def test_sqlite_project_shows_sqlite_section_skips_postgres_and_redis(tmp_path):
    """For a project on SQLite with no Redis cache, the banner must not
    mention PostgreSQL or Redis; it must point at the sqlite file and
    show the ``sqlite3`` invocation a user / coding agent can run.
    """

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    db_path = tmp_path / "db.sqlite3"
    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": db_path,
            },
        },
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
    assert "SQLite" in result
    assert f"sqlite3 {db_path}" in result or f"sqlite3 '{db_path}'" in result
    assert "PostgreSQL" not in result
    assert "psql" not in result
    assert "Redis" not in result
    assert "redis-cli" not in result


def test_sqlite_in_memory_shown_with_django_shell_hint(tmp_path):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
    assert "in-memory" in result
    assert "manage.py shell" in result
    # No sqlite3 CLI invocation when there's no on-disk file.
    assert "sqlite3 " not in result


def test_postgres_project_with_no_redis_skips_redis_section(tmp_path):
    """A Postgres-but-no-Redis project should not advertise a Redis
    section in the banner."""

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "127.0.0.1",
                "PORT": "5432",
                "NAME": "demo",
                "USER": "demo",
                "PASSWORD": "demo-pwd",
            },
        },
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
    assert "PostgreSQL" in result
    assert "Redis" not in result
    assert "redis-cli" not in result


def test_postgres_with_redis_renders_both_sections(tmp_path):
    """Sanity: when both services are present, both sections render —
    confirms our skip-logic doesn't accidentally hide healthy sections.
    """

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "127.0.0.1",
                "PORT": "5432",
                "NAME": "demo",
                "USER": "demo",
                "PASSWORD": "demo-pwd",
            },
        },
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://127.0.0.1:6379/0",
            },
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        os.environ["DEV_HELPERS_PORT"] = "8000"
        try:
            result = render_template(cfg)
        finally:
            os.environ.pop("DEV_HELPERS_PORT", None)
    assert "PostgreSQL" in result
    assert "Redis" in result
    assert "redis-cli" in result


def test_render_template_with_unknown_port_uses_placeholder(tmp_path):
    """When the prompt is rendered *before* the dev server has picked a
    port (e.g. ``manage.py run_site`` printing a suggestion block while
    run-site itself hasn't started yet), ``discover_port`` legitimately
    returns ``None``. The rendered output must not say
    ``http://localhost:None`` — it should fall back to the ``$PORT``
    placeholder so the copy-pasted line stays correct once shell
    expansion fills it in from the dotfile."""

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_template

    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        # No DEV_HELPERS_PORT, no runserver in argv, no sidecar → port is None.
        result = render_template(cfg)
    assert ":None" not in result
    assert "http://localhost:$PORT" in result


def test_static_block_for_sqlite_project_omits_postgres_and_redis(tmp_path):
    """The AGENTS.md / CLAUDE.md static block follows the same rule:
    only document the services the project actually uses."""

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.prompt import render_static_agent_help_block

    db_path = tmp_path / "db.sqlite3"
    _clear_dev_helpers_env()
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "settings"},
            "dotfiles": {"directory": str(tmp_path)},
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": db_path,
            },
        },
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        },
    ):
        reset_config()
        cfg = DevHelpersConfig()
        block = render_static_agent_help_block(cfg)
    assert "### SQLite" in block
    assert str(db_path) in block
    assert "### PostgreSQL" not in block
    assert "### Redis" not in block
