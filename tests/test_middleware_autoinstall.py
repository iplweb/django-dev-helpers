from __future__ import annotations

from unittest.mock import patch

from django.test import override_settings

_AUTOLOGIN_MW = "django_dev_helpers.middleware.AutologinMiddleware"


def _call_install(cfg_overrides=None, middleware=None):
    """Run the auto-install routine against a synthesized config + MIDDLEWARE."""
    from django_dev_helpers import apps as apps_module
    from django_dev_helpers.conf import reset_config

    overrides = {
        "enabled": True,
        "autologin": {"allowed_hosts": ["testserver"]},
    }
    if cfg_overrides:
        overrides.update(cfg_overrides)
    mw_list = (
        middleware
        if middleware is not None
        else [
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ]
    )
    with override_settings(DJANGO_DEV_HELPERS=overrides, MIDDLEWARE=mw_list):
        reset_config()
        from django_dev_helpers.conf import get_config

        apps_module.install_autologin_middleware_if_enabled(get_config())
        from django.conf import settings

        return list(settings.MIDDLEWARE)


def test_autoinstall_appends_at_end_of_middleware():
    """Appending at the end ensures every preceding middleware
    (Session, Auth, Messages) has set up request state by the time our
    middleware (and therefore the autologin view) runs -- in particular
    ``request._messages``, which the view writes to when
    ``autologin.flash_message`` is configured."""
    final = _call_install()
    assert final[-1] == _AUTOLOGIN_MW


def test_autoinstall_skipped_when_already_present():
    pre = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        _AUTOLOGIN_MW,
        "django.contrib.auth.middleware.AuthenticationMiddleware",
    ]
    final = _call_install(middleware=pre)
    assert final == pre  # exactly one occurrence, untouched


def test_autoinstall_skipped_when_flag_false():
    final = _call_install(
        cfg_overrides={
            "enabled": True,
            "autologin": {
                "middleware_autoinstall": False,
                "allowed_hosts": ["testserver"],
            },
        }
    )
    assert _AUTOLOGIN_MW not in final


def test_autoinstall_skipped_when_autologin_disabled():
    final = _call_install(
        cfg_overrides={
            "enabled": True,
            "autologin": {"enabled": False},
        }
    )
    assert _AUTOLOGIN_MW not in final


def test_autoinstall_appends_when_no_auth_middleware_present():
    pre = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ]
    final = _call_install(middleware=pre)
    assert final[-1] == _AUTOLOGIN_MW


def test_autoinstall_handles_tuple_middleware():
    """settings.MIDDLEWARE is sometimes declared as a tuple; the routine
    must accept that without crashing."""
    from django_dev_helpers import apps as apps_module
    from django_dev_helpers.conf import get_config, reset_config

    with override_settings(
        DJANGO_DEV_HELPERS={"enabled": True, "autologin": {"allowed_hosts": ["testserver"]}},
        MIDDLEWARE=(
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
        ),
    ):
        reset_config()
        apps_module.install_autologin_middleware_if_enabled(get_config())
        from django.conf import settings

        assert _AUTOLOGIN_MW in settings.MIDDLEWARE


def test_middleware_autoinstall_flag_must_be_bool():
    from django.core.exceptions import ImproperlyConfigured

    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"autologin": {"middleware_autoinstall": "yes"}}),
        patch.object(DevHelpersConfig, "__init__", DevHelpersConfig.__init__),
    ):
        try:
            DevHelpersConfig()
        except ImproperlyConfigured as exc:
            assert "middleware_autoinstall" in str(exc)
            return
    raise AssertionError("Expected ImproperlyConfigured for non-bool middleware_autoinstall")
