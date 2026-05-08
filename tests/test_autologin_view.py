import os

import pytest
from django.test import RequestFactory, override_settings


def test_valid_token_logs_in(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == "/"


def test_valid_token_logs_in_user(client, admin_user, autologin_token):
    from django.contrib.auth.models import User

    url = f"/__autologin__/?token={autologin_token}"
    client.get(url)
    assert User.objects.filter(username="admin").exists()


def test_invalid_token_404(client, admin_user, autologin_token):
    url = "/__autologin__/?token=wrong-token"
    response = client.get(url)
    assert response.status_code == 404


def test_missing_token_env_404(client, admin_user):
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)
    url = "/__autologin__/?token=something"
    response = client.get(url)
    assert response.status_code == 404


def test_missing_user_404(client, db, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.get(url)
    assert response.status_code == 404


def test_refuses_non_localhost_host(admin_user, autologin_token):
    from unittest.mock import patch

    from django_dev_helpers.views import autologin

    factory = RequestFactory()
    request = factory.get(f"/__autologin__/?token={autologin_token}")
    from django.http import Http404

    with (
        override_settings(ALLOWED_HOSTS=["*", "evil.example.com"]),
        patch.object(request, "get_host", return_value="evil.example.com"),
        pytest.raises(Http404),
    ):
        autologin(request)


def test_accepts_localhost(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.get(url, SERVER_NAME="localhost")
    assert response.status_code == 302


def test_extra_cookies_set(client, admin_user, autologin_token):
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "autologin": {
                "allowed_hosts": ["testserver"],
                "extra_cookies": [
                    {
                        "name": "test_cookie",
                        "value": "1",
                        "max_age": 3600,
                        "samesite": "Lax",
                        "path": "/",
                        "secure": False,
                        "httponly": False,
                    },
                ],
            },
        }
    ):
        from django_dev_helpers.conf import reset_config
        reset_config()
        url = f"/__autologin__/?token={autologin_token}"
        response = client.get(url)
        assert response.status_code == 302
        assert "test_cookie" in response.cookies


def test_flash_message(client, admin_user, autologin_token):
    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "autologin": {
                "allowed_hosts": ["testserver"],
                "flash_message": "Welcome!",
            },
        }
    ):
        from django_dev_helpers.conf import reset_config
        reset_config()
        url = f"/__autologin__/?token={autologin_token}"
        response = client.get(url)
        assert response.status_code == 302
