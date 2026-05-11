from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import override_settings


def _middleware_with(get_response):
    from django_dev_helpers.middleware import AutologinMiddleware

    return AutologinMiddleware(get_response)


def test_middleware_intercepts_autologin_path_and_logs_in(client, admin_user, autologin_token):
    """End-to-end: with ROOT_URLCONF that doesn't wire autologin, the
    middleware alone makes ``/__autologin__/?token=...`` work."""
    with override_settings(
        ROOT_URLCONF="tests.empty_urls",
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django_dev_helpers.middleware.AutologinMiddleware",
        ],
    ):
        response = client.get(f"/__autologin__/?token={autologin_token}")
    assert response.status_code == 302
    assert response.url == "/"


def test_middleware_passes_through_other_paths(client, admin_user, autologin_token):
    with override_settings(
        ROOT_URLCONF="tests.empty_urls",
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django_dev_helpers.middleware.AutologinMiddleware",
        ],
    ):
        response = client.get("/some/other/path/")
    # No URL matches, so Django returns its normal 404 -- proves the
    # middleware did NOT swallow unrelated requests.
    assert response.status_code == 404


def test_middleware_does_nothing_when_autologin_disabled():
    """Disabled autologin means the middleware must be a no-op pass-through."""
    sentinel_response = object()
    get_response = MagicMock(return_value=sentinel_response)
    mw = _middleware_with(get_response)

    request = SimpleNamespace(path="/__autologin__/")
    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "autologin": {"enabled": False}}):
        from django_dev_helpers.conf import reset_config

        reset_config()
        out = mw(request)
    assert out is sentinel_response
    get_response.assert_called_once_with(request)


def test_middleware_does_nothing_when_package_inactive():
    sentinel = object()
    get_response = MagicMock(return_value=sentinel)
    mw = _middleware_with(get_response)

    request = SimpleNamespace(path="/__autologin__/")
    with override_settings(DJANGO_DEV_HELPERS={"enabled": False}):
        from django_dev_helpers.conf import reset_config

        reset_config()
        out = mw(request)
    assert out is sentinel


def test_middleware_refuses_to_init_when_debug_false():
    """Defense in depth: refuse to load when DEBUG=False so an accidental
    production deploy can't expose the token-gated login backdoor."""
    import pytest
    from django.core.exceptions import ImproperlyConfigured

    from django_dev_helpers.middleware import AutologinMiddleware

    with override_settings(DEBUG=False), pytest.raises(ImproperlyConfigured, match="DEBUG=True"):
        AutologinMiddleware(lambda r: r)


def test_middleware_matches_configured_url_path(client, admin_user, autologin_token):
    """A project that customizes ``autologin.url_path`` should have the
    middleware honor the new path, not the default."""
    with override_settings(
        ROOT_URLCONF="tests.empty_urls",
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django_dev_helpers.middleware.AutologinMiddleware",
        ],
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "autologin": {
                "url_path": "secret-login/",
                "allowed_hosts": ["testserver"],
            },
        },
    ):
        from django_dev_helpers.conf import reset_config

        reset_config()
        response = client.get(f"/secret-login/?token={autologin_token}")
    assert response.status_code == 302
