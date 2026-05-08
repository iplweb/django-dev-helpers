from __future__ import annotations

import os

import pytest
from django.test import override_settings


@pytest.fixture
def sidecar_dir(tmp_path):
    return tmp_path


_DEFAULT_PG = {
    "host": "127.0.0.1",
    "port": 5432,
    "db": "myproj",
    "user": "myproj",
    "password": "p@ss'word",
}


def _write_sidecar(path, **kwargs):
    pg = kwargs.get("pg", _DEFAULT_PG)
    redis = kwargs.get("redis", {"host": "127.0.0.1", "port": 6379, "db": 0})
    web = kwargs.get("web", {"host": "127.0.0.1", "port": 49152})
    lines = [
        'project_slug = "myproj"',
        'generated_at = "2026-05-08T05:48:00+00:00"',
        "",
        "[web]",
        f'host = "{web["host"]}"',
        f"port = {web['port']}",
        "",
        "[postgres]",
        f'host = "{pg["host"]}"',
        f"port = {pg['port']}",
        f'db = "{pg["db"]}"',
        f'user = "{pg["user"]}"',
        f'password = "{pg["password"]}"',
        "",
        "[redis]",
        f'host = "{redis["host"]}"',
        f"port = {redis['port']}",
        f"db = {redis['db']}",
        "",
        "[celery]",
        "enabled = false",
    ]
    (path / ".run-site-config").write_text("\n".join(lines), encoding="utf-8")


def test_read_sidecar_missing_returns_none(sidecar_dir):
    from django_dev_helpers import sidecar

    assert sidecar.read_sidecar(sidecar_dir) is None


def test_read_sidecar_malformed_returns_none(sidecar_dir, caplog):
    import logging

    (sidecar_dir / ".run-site-config").write_text("not = valid = toml", encoding="utf-8")
    from django_dev_helpers import sidecar

    with caplog.at_level(logging.WARNING):
        assert sidecar.read_sidecar(sidecar_dir) is None
    assert any("failed to read sidecar" in rec.message for rec in caplog.records)


def test_extract_endpoints(sidecar_dir):
    _write_sidecar(sidecar_dir)
    from django_dev_helpers import sidecar

    data = sidecar.read_sidecar(sidecar_dir)
    assert data is not None
    out = sidecar.extract_endpoints(data)
    assert out["pg_host"] == "127.0.0.1"
    assert out["pg_port"] == 5432
    assert out["db_name"] == "myproj"
    assert out["db_user"] == "myproj"
    assert out["db_password"] == "p@ss'word"
    assert out["redis_host"] == "127.0.0.1"
    assert out["redis_port"] == 6379
    assert out["web_port"] == 49152


def test_resolve_db_info_uses_sidecar_in_auto(sidecar_dir):
    """When env is unset and sidecar is present, auto mode reads sidecar."""
    _write_sidecar(sidecar_dir)
    for key in ("DEV_HELPERS_DB_HOST", "DEV_HELPERS_DB_PORT"):
        os.environ.pop(key, None)
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "lookup": {"source": "auto"},
            "dotfiles": {"directory": str(sidecar_dir)},
        },
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3"}},
    ):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.dotfiles import resolve_db_info

        reset_config()
        cfg = DevHelpersConfig()
        info = resolve_db_info(cfg)
        assert info["pg_host"] == "127.0.0.1"
        assert info["pg_port"] == 5432
        assert info["db_password"] == "p@ss'word"


def test_env_beats_sidecar_in_auto(sidecar_dir):
    _write_sidecar(sidecar_dir)
    os.environ["DEV_HELPERS_DB_HOST"] = "from-env"
    os.environ["DEV_HELPERS_DB_PORT"] = "9999"
    try:
        with override_settings(
            DJANGO_DEV_HELPERS={
                "enabled": True,
                "lookup": {"source": "auto"},
                "dotfiles": {"directory": str(sidecar_dir)},
            }
        ):
            from django_dev_helpers.conf import DevHelpersConfig, reset_config
            from django_dev_helpers.dotfiles import resolve_pg_endpoint

            reset_config()
            cfg = DevHelpersConfig()
            assert resolve_pg_endpoint(cfg) == ("from-env", 9999)
    finally:
        os.environ.pop("DEV_HELPERS_DB_HOST", None)
        os.environ.pop("DEV_HELPERS_DB_PORT", None)


def test_lookup_source_sidecar_only(sidecar_dir):
    _write_sidecar(sidecar_dir)
    os.environ["DEV_HELPERS_DB_HOST"] = "should-be-ignored"
    os.environ["DEV_HELPERS_DB_PORT"] = "1"
    try:
        with override_settings(
            DJANGO_DEV_HELPERS={
                "enabled": True,
                "lookup": {"source": "sidecar"},
                "dotfiles": {"directory": str(sidecar_dir)},
            }
        ):
            from django_dev_helpers.conf import DevHelpersConfig, reset_config
            from django_dev_helpers.dotfiles import resolve_pg_endpoint

            reset_config()
            cfg = DevHelpersConfig()
            assert resolve_pg_endpoint(cfg) == ("127.0.0.1", 5432)
    finally:
        os.environ.pop("DEV_HELPERS_DB_HOST", None)
        os.environ.pop("DEV_HELPERS_DB_PORT", None)
