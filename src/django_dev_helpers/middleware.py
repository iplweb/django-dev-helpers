"""Middleware that intercepts the autologin URL.

Provides an alternative to wiring ``*autologin_urlpatterns()`` into the
project ``urls.py``: install this middleware (or let django-dev-helpers
auto-install it on app startup, which is the default in dev) and the
autologin endpoint works without any URLconf changes.

Order: place after ``django.contrib.sessions.middleware.SessionMiddleware``
and ``django.contrib.auth.middleware.AuthenticationMiddleware`` so that
the auth-login call inside the view sees a usable session backend. The
auto-installer inserts the entry immediately after
``AuthenticationMiddleware`` when it is present, otherwise appends to the
end of ``MIDDLEWARE``.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class AutologinMiddleware:
    def __init__(self, get_response):
        # Defense in depth: this middleware exposes a token-gated login
        # backdoor. The package's app.ready() already refuses to activate
        # without DEBUG=True when serving HTTP, but a user could still
        # paste this middleware path into ``MIDDLEWARE`` without
        # django-dev-helpers in ``INSTALLED_APPS``, or flip ``DEBUG`` off
        # at the wrong moment. Fail loud and early in either case rather
        # than silently serving requests in production.
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "django_dev_helpers.middleware.AutologinMiddleware requires "
                "settings.DEBUG=True. This middleware exposes a token-gated "
                "login backdoor and is not safe to run in production. Remove "
                "it from MIDDLEWARE for non-dev deployments."
            )
        self.get_response = get_response

    def __call__(self, request):
        from .conf import get_config

        cfg = get_config()
        if cfg.is_active() and cfg.autologin.enabled:
            target = "/" + cfg.autologin.url_path.lstrip("/")
            if request.path == target:
                from .views import autologin

                return autologin(request)
        return self.get_response(request)
