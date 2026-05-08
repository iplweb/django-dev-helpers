import os

import pytest
from django.contrib.auth.models import User


@pytest.fixture(autouse=True)
def _reset_config():
    from django_dev_helpers.conf import reset_config

    reset_config()
    yield
    reset_config()


@pytest.fixture(autouse=True)
def _setup_env():
    os.environ.setdefault("DJANGO_DEV_HELPERS_ENABLED", "1")
    yield
    for key in [
        "DJANGO_DEV_HELPERS_ENABLED",
        "DEV_HELPERS_AUTOLOGIN_TOKEN",
        "DEV_HELPERS_PORT",
        "DEV_HELPERS_DB_HOST",
        "DEV_HELPERS_DB_PORT",
        "DEV_HELPERS_REDIS_HOST",
        "DEV_HELPERS_REDIS_PORT",
        "DEV_HELPERS_PROJECT_ROOT",
        "DJANGO_DEV_HELPERS_FORCE_SAFETY_CHECK",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def autologin_token():
    token = "test-token-abc123"
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = token
    yield token
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin", email="admin@test.com", password="password")
