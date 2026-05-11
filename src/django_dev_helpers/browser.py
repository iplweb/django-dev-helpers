from __future__ import annotations

import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from django_dev_helpers import dotfiles, tokens

logger = logging.getLogger(__name__)


def is_headless() -> bool:
    """Heuristic: don't try to open a browser in obviously-headless contexts.

    Linux without DISPLAY/WAYLAND_DISPLAY is the common case. macOS and
    Windows have system-default browser launchers, so we don't filter
    them here.
    """
    if sys.platform.startswith("linux"):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return True
    return False


def _build_autologin_url(cfg, host: str, port: str) -> str:
    token = tokens.current_token()
    return f"http://{host}:{port}/{cfg.autologin.url_path}?token={token}"


def _probe_autologin_status(cfg, host: str, port: str) -> int | None:
    """HEAD-probe the autologin URL and return its HTTP status.

    HEAD is used because the autologin view is restricted to GET via
    ``@require_http_methods(["GET"])``: a *wired* URL responds with 405
    (method not allowed), while an *unmounted* URL bubbles up as 404 from
    Django's URL resolver. The 404-vs-not-404 split is therefore a reliable
    "is autologin wired?" signal, and HEAD avoids triggering the real login
    side effect (session creation, ``last_login`` update, audit log entry).

    Returns the HTTP status code, or ``None`` on connection error (e.g.
    server not actually up yet -- in which case we want to leave the URL
    decision as-is rather than show a false-positive banner).
    """
    path = cfg.autologin.url_path.lstrip("/")
    url = f"http://{host}:{port}/{path}"
    request = urllib.request.Request(url, method="HEAD")
    try:
        response = urllib.request.urlopen(request, timeout=2)
        return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None


def _print_autologin_not_wired_banner(cfg, host: str, port: str) -> None:
    """Tell the user (and any watching coding agent) how to wire the URL.

    Reached when the HEAD-probe to the autologin URL returns 404. With the
    default ``middleware_autoinstall=True`` this should normally never fire,
    so the banner walks the user through the most likely causes (auto-install
    disabled, app config missing, etc.) instead of just repeating one fix.
    """
    autologin_path = cfg.autologin.url_path.lstrip("/")
    message = (
        "\n"
        "─── django-dev-helpers ───────────────────────────────────────────────\n"
        f"  Autologin endpoint /{autologin_path} returned 404.\n"
        "  The autologin URL is not reachable -- check one of these:\n"
        "\n"
        "  1. Make sure 'django_dev_helpers' is in INSTALLED_APPS. The package\n"
        "     auto-installs its middleware on app startup; if the app isn't\n"
        "     loaded, the middleware never runs.\n"
        "\n"
        "  2. If you set autologin.middleware_autoinstall=False, you must\n"
        "     either install the middleware manually:\n"
        "\n"
        "        MIDDLEWARE = [\n"
        "            ...,\n"
        "            'django_dev_helpers.middleware.AutologinMiddleware',\n"
        "        ]\n"
        "\n"
        "     ...or wire the URL pattern explicitly in your project urls.py:\n"
        "\n"
        "        from django_dev_helpers.urls import autologin_urlpatterns\n"
        "        urlpatterns = [..., *autologin_urlpatterns()]\n"
        "\n"
        "  3. To disable autologin entirely:\n"
        "        DJANGO_DEV_HELPERS = {'autologin': {'enabled': False}}\n"
        "\n"
        f"  Opening http://{host}:{port}/ instead of the autologin URL.\n"
        "──────────────────────────────────────────────────────────────────────\n"
    )
    sys.stderr.write(message)
    sys.stderr.flush()


def open_browser(cfg) -> None:
    host = dotfiles.discover_bind_host(cfg)
    if host in ("0.0.0.0", ""):
        host = "localhost"
    port = dotfiles.discover_port(cfg) or "8000"

    if cfg.browser_open.url_path is not None:
        url = f"http://{host}:{port}{cfg.browser_open.url_path}"
    elif cfg.autologin.enabled:
        status = _probe_autologin_status(cfg, host, port)
        if status == 404:
            _print_autologin_not_wired_banner(cfg, host, port)
            url = f"http://{host}:{port}/"
        else:
            url = _build_autologin_url(cfg, host, port)
    else:
        url = f"http://{host}:{port}/"

    logger.info("django-dev-helpers: opening browser at %s", url)
    webbrowser.open(url)


def wait_for_http(cfg) -> None:
    host = dotfiles.discover_bind_host(cfg)
    if host in ("0.0.0.0", ""):
        host = "localhost"
    port = dotfiles.discover_port(cfg) or "8000"
    probe_path = cfg.browser_open.probe_path or "/admin/login/"
    url = f"http://{host}:{port}{probe_path}"
    timeout = cfg.browser_open.probe_timeout_seconds or 30.0

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = urllib.request.urlopen(url, timeout=2)
            if response.status < 500:
                open_browser(cfg)
                return
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                open_browser(cfg)
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.5)

    logger.warning(
        "django-dev-helpers: self-probe timed out after %ss, not opening browser",
        timeout,
    )


def spawn_self_probe_thread(cfg) -> None:
    if is_headless():
        logger.info("django-dev-helpers: headless environment detected, skipping browser open")
        return
    t = threading.Thread(
        target=wait_for_http,
        args=(cfg,),
        name="dev-helpers-self-probe",
        daemon=True,
    )
    t.start()
