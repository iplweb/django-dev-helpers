import os

from django.test import override_settings


def test_resolve_pg_from_env():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.dotfiles import resolve_pg_endpoint

    os.environ["DEV_HELPERS_DB_HOST"] = "db.example.com"
    os.environ["DEV_HELPERS_DB_PORT"] = "5433"
    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "env"}}):
        cfg = DevHelpersConfig()
        result = resolve_pg_endpoint(cfg)
        assert result == ("db.example.com", 5433)
    os.environ.pop("DEV_HELPERS_DB_HOST", None)
    os.environ.pop("DEV_HELPERS_DB_PORT", None)


def test_resolve_pg_from_settings():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.dotfiles import resolve_pg_endpoint

    os.environ.pop("DEV_HELPERS_DB_HOST", None)
    os.environ.pop("DEV_HELPERS_DB_PORT", None)
    with override_settings(
        DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "settings"}},
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "127.0.0.1",
                "PORT": "5432",
            },
        },
    ):
        cfg = DevHelpersConfig()
        result = resolve_pg_endpoint(cfg)
        assert result == ("127.0.0.1", 5432)


def test_resolve_redis_from_env():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.dotfiles import resolve_redis_endpoint

    os.environ["DEV_HELPERS_REDIS_HOST"] = "redis.example.com"
    os.environ["DEV_HELPERS_REDIS_PORT"] = "6380"
    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "env"}}):
        cfg = DevHelpersConfig()
        result = resolve_redis_endpoint(cfg)
        assert result == ("redis.example.com", 6380)
    os.environ.pop("DEV_HELPERS_REDIS_HOST", None)
    os.environ.pop("DEV_HELPERS_REDIS_PORT", None)


def test_auto_source_env_wins():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.dotfiles import resolve_pg_endpoint

    os.environ["DEV_HELPERS_DB_HOST"] = "from-env"
    os.environ["DEV_HELPERS_DB_PORT"] = "9999"
    with override_settings(
        DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "auto"}},
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "from-settings",
                "PORT": "5432",
            },
        },
    ):
        cfg = DevHelpersConfig()
        result = resolve_pg_endpoint(cfg)
        assert result == ("from-env", 9999)
    os.environ.pop("DEV_HELPERS_DB_HOST", None)
    os.environ.pop("DEV_HELPERS_DB_PORT", None)


def test_resolve_returns_none_when_nothing():
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.dotfiles import resolve_pg_endpoint

    os.environ.pop("DEV_HELPERS_DB_HOST", None)
    os.environ.pop("DEV_HELPERS_DB_PORT", None)
    with override_settings(
        DJANGO_DEV_HELPERS={"enabled": True, "lookup": {"source": "settings"}},
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3"}},
    ):
        cfg = DevHelpersConfig()
        result = resolve_pg_endpoint(cfg)
        assert result is None
