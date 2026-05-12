"""Middleware that handles autologin on any URL.

Two responsibilities:

1. **Path interception.** Catch requests to the configured autologin URL
   (``cfg.autologin.url_path``) and route them to the autologin view. This
   removes the need to wire ``*autologin_urlpatterns()`` into the project
   ``urls.py``. The auto-installer in ``apps.py`` adds this middleware to
   ``settings.MIDDLEWARE`` on app startup (gated by
   ``autologin.middleware_autoinstall``).

2. **Query-param toggles.** Watch every request for
   ``?<query_param>=<action>``. Three actions are recognised:

   - ``tmp_off`` -- render the current request as if the user were
     anonymous (``request.user = AnonymousUser()``). The session is left
     intact, so the next request without the toggle is again
     authenticated. The toggle param is stripped from ``request.GET`` so
     downstream views see a clean query string.
   - ``logout`` -- ``django.contrib.auth.logout(request)``. Returns a
     302 to the same path, sans the toggle param, with any other query
     parameters preserved.
   - ``log_in`` (or ``login``) -- log the configured user in (uses
     ``autologin.user_lookup_field`` / ``user_lookup_value``). No URL
     token required: localhost trust is sufficient because the host
     allowlist (``refuse_if_unsafe_host``) already gates the toggle.
     Returns a 302 to the cleaned URL.

Any other toggle value is ignored (the request flows through normally).
The toggle name is configurable via ``autologin.query_param``; set it to
empty string or ``None`` to disable the toggle layer entirely.

Order: append at the end of ``MIDDLEWARE`` (what the auto-installer
does). The toggles work as long as the middleware runs *after*
``SessionMiddleware`` and ``AuthenticationMiddleware`` (sessions for
``logout``/``log_in``; ``request.user`` already set up so ``tmp_off``
can replace it). ``MessageMiddleware`` must also have run, because the
path-based autologin view writes to ``request._messages`` when
``flash_message`` is configured.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponseRedirect

_TOGGLE_TMP_OFF = "tmp_off"
_TOGGLE_LOGOUT = "logout"
_TOGGLE_LOG_IN_VALUES = ("log_in", "login")


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
        if not (cfg.is_active() and cfg.autologin.enabled):
            return self.get_response(request)

        target = "/" + cfg.autologin.url_path.lstrip("/")
        if request.path == target:
            from .views import autologin

            return autologin(request)

        query_param = cfg.autologin.query_param
        if query_param:
            action = request.GET.get(query_param)
            if action:
                handled = self._dispatch_toggle(request, cfg, action, query_param)
                if handled is not None:
                    return handled

        return self.get_response(request)

    def _dispatch_toggle(self, request, cfg, action, query_param):
        """Return a response if ``action`` is a recognised toggle and the
        host allowlist permits it, otherwise ``None`` so the caller falls
        through to ``get_response``."""
        try:
            cfg.refuse_if_unsafe_host(request)
        except Http404:
            # Off-localhost requests must look identical to a normal pass
            # through; do not redirect, do not log in, do not 404 (that
            # would leak the toggle's existence).
            return None

        if action == _TOGGLE_TMP_OFF:
            return self._anonymize(request, query_param)
        if action == _TOGGLE_LOGOUT:
            from django.contrib.auth import logout

            logout(request)
            return HttpResponseRedirect(_clean_url(request, query_param))
        if action in _TOGGLE_LOG_IN_VALUES:
            return self._login_and_redirect(request, cfg, query_param)
        # Unknown action: silently pass through (probably a typo on the
        # user's part; logging or 400 would be noisier than helpful).
        return None

    def _anonymize(self, request, query_param):
        """Render this single request as anonymous, leave the session
        alone, and hide the toggle param from downstream views."""
        request.user = AnonymousUser()
        new_get = request.GET.copy()
        new_get.pop(query_param, None)
        request.GET = new_get
        return self.get_response(request)

    def _login_and_redirect(self, request, cfg, query_param):
        from django.contrib.auth import get_user_model, login

        user_model = get_user_model()
        try:
            user = user_model.objects.get(**{cfg.autologin.user_lookup_field: cfg.autologin.user_lookup_value})
        except (user_model.DoesNotExist, user_model.MultipleObjectsReturned) as exc:
            raise Http404() from exc
        login(request, user, backend=cfg.autologin.auth_backend)
        return HttpResponseRedirect(_clean_url(request, query_param))


def _clean_url(request, query_param):
    """Build a redirect URL for the current request with ``query_param``
    removed. All other query parameters are preserved."""
    new_get = request.GET.copy()
    new_get.pop(query_param, None)
    encoded = new_get.urlencode()
    if encoded:
        return f"{request.path}?{encoded}"
    return request.path
