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


def open_browser(cfg) -> None:
    host = dotfiles.discover_bind_host(cfg)
    if host in ("0.0.0.0", ""):
        host = "localhost"
    port = dotfiles.discover_port(cfg) or "8000"

    if cfg.browser_open.url_path is None:
        url = _build_autologin_url(cfg, host, port) if cfg.autologin.enabled else f"http://{host}:{port}/"
    else:
        url = f"http://{host}:{port}{cfg.browser_open.url_path}"

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
