"""Tests for the ?__autologin__=tmp_off / logout / log_in toggles."""

from __future__ import annotations

from django.test import override_settings

_MIDDLEWARE_WITH_AUTOLOGIN = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_dev_helpers.middleware.AutologinMiddleware",
]


def _whoami_urls():
    """A tiny URLconf that echoes whether request.user is authenticated."""
    return "tests.toggle_urls"


def test_tmp_off_renders_request_as_anonymous(client, admin_user, autologin_token):
    """A logged-in browser visiting ``?__autologin__=tmp_off`` should see
    the page rendered with request.user = AnonymousUser, but the next
    request (without the param) should still be logged in."""
    # Establish a logged-in session.
    login_url = f"/__autologin__/?token={autologin_token}"
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        r = client.get(login_url)
        assert r.status_code == 302
        # Sanity: subsequent request is authenticated.
        r = client.get("/whoami/")
        assert r.content == b"authenticated"

        r = client.get("/whoami/?__autologin__=tmp_off")
        assert r.content == b"anonymous"

        # Session is unchanged: next plain request is still authenticated.
        r = client.get("/whoami/")
        assert r.content == b"authenticated"


def test_logout_ends_session_and_redirects(client, admin_user, autologin_token):
    login_url = f"/__autologin__/?token={autologin_token}"
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        client.get(login_url)
        r = client.get("/whoami/?__autologin__=logout")
        assert r.status_code == 302
        # Redirect target is the same path without the toggle param.
        assert r.url == "/whoami/"

        # Subsequent plain request: anonymous.
        r = client.get("/whoami/")
        assert r.content == b"anonymous"


def test_log_in_logs_in_configured_user(client, admin_user):
    """A request to any URL with ``?__autologin__=log_in`` should log in
    the user configured via ``autologin.user_lookup_value`` even though
    the session has never been authenticated and the URL carries no
    token (we trust the localhost host allowlist for this short URL)."""
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        # Sanity: starting state is anonymous.
        r = client.get("/whoami/")
        assert r.content == b"anonymous"

        r = client.get("/whoami/?__autologin__=log_in")
        assert r.status_code == 302
        assert r.url == "/whoami/"

        r = client.get("/whoami/")
        assert r.content == b"authenticated"


def test_log_in_after_logout_round_trip(client, admin_user):
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        client.get("/whoami/?__autologin__=log_in")
        client.get("/whoami/?__autologin__=logout")
        r = client.get("/whoami/")
        assert r.content == b"anonymous"
        client.get("/whoami/?__autologin__=log_in")
        r = client.get("/whoami/")
        assert r.content == b"authenticated"


def test_toggle_redirect_preserves_other_query_params(client, admin_user, autologin_token):
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        client.get(f"/__autologin__/?token={autologin_token}")
        r = client.get("/whoami/?__autologin__=logout&page=2&sort=name")
        assert r.status_code == 302
        # Either order is fine; the param we care about must be gone and
        # the rest must remain.
        assert "__autologin__" not in r.url
        assert "page=2" in r.url
        assert "sort=name" in r.url


def test_unknown_toggle_value_passes_through(client, admin_user, autologin_token):
    """A nonsense value (typo) should not redirect or log anyone in/out."""
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        client.get(f"/__autologin__/?token={autologin_token}")
        r = client.get("/whoami/?__autologin__=garbage")
        assert r.status_code == 200
        assert r.content == b"authenticated"


def test_toggles_disabled_when_query_param_empty(client, admin_user, autologin_token):
    overrides = {
        "enabled": True,
        "autologin": {
            "allowed_hosts": ["testserver"],
            "query_param": "",
        },
    }
    with override_settings(
        DJANGO_DEV_HELPERS=overrides,
        ROOT_URLCONF=_whoami_urls(),
        MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN,
    ):
        from django_dev_helpers.conf import reset_config

        reset_config()
        client.get(f"/__autologin__/?token={autologin_token}")
        # With toggles disabled, ?__autologin__=logout has no effect.
        r = client.get("/whoami/?__autologin__=logout")
        assert r.status_code == 200
        assert r.content == b"authenticated"


def test_toggles_respect_custom_query_param_name(client, admin_user, autologin_token):
    overrides = {
        "enabled": True,
        "autologin": {
            "allowed_hosts": ["testserver"],
            "query_param": "_auth",
        },
    }
    with override_settings(
        DJANGO_DEV_HELPERS=overrides,
        ROOT_URLCONF=_whoami_urls(),
        MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN,
    ):
        from django_dev_helpers.conf import reset_config

        reset_config()
        client.get(f"/__autologin__/?token={autologin_token}")
        r = client.get("/whoami/?_auth=logout")
        assert r.status_code == 302
        r = client.get("/whoami/")
        assert r.content == b"anonymous"


def test_query_param_must_be_str_or_none():
    """Validation: non-string non-None values rejected at config load."""
    import pytest
    from django.core.exceptions import ImproperlyConfigured

    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"autologin": {"query_param": 42}}),
        pytest.raises(ImproperlyConfigured, match="query_param"),
    ):
        DevHelpersConfig()


def test_tmp_off_strips_param_from_request_get(client, admin_user, autologin_token):
    """Downstream views should not see the magic param leaked into GET."""
    with override_settings(ROOT_URLCONF=_whoami_urls(), MIDDLEWARE=_MIDDLEWARE_WITH_AUTOLOGIN):
        client.get(f"/__autologin__/?token={autologin_token}")
        r = client.get("/echo/?__autologin__=tmp_off&page=3")
        # The echo view reports request.GET keys joined by commas.
        assert r.status_code == 200
        assert r.content == b"page"
