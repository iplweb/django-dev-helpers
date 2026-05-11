from __future__ import annotations

import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django_dev_helpers import browser


def _make_cfg(probe_timeout_seconds=0.1, autologin_enabled=False, browser_url_path=None):
    return SimpleNamespace(
        browser_open=SimpleNamespace(
            enabled=True,
            url_path=browser_url_path,
            probe_path="/admin/login/",
            probe_timeout_seconds=probe_timeout_seconds,
        ),
        autologin=SimpleNamespace(enabled=autologin_enabled, url_path="dev-helpers/autologin/"),
    )


def test_wait_for_http_opens_browser_on_200():
    cfg = _make_cfg()
    response = MagicMock()
    response.status = 200

    with (
        patch.object(browser.urllib.request, "urlopen", return_value=response) as urlopen,
        patch.object(browser, "open_browser") as open_browser,
        patch.object(browser.time, "sleep"),
    ):
        browser.wait_for_http(cfg)

    assert urlopen.called
    open_browser.assert_called_once_with(cfg)


def test_wait_for_http_opens_browser_on_404_httperror():
    cfg = _make_cfg()
    http_error = urllib.error.HTTPError(
        url="http://localhost:8000/admin/login/",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )

    with (
        patch.object(browser.urllib.request, "urlopen", side_effect=http_error) as urlopen,
        patch.object(browser, "open_browser") as open_browser,
        patch.object(browser.time, "sleep"),
    ):
        browser.wait_for_http(cfg)

    assert urlopen.called
    open_browser.assert_called_once_with(cfg)


def test_wait_for_http_retries_on_503_then_times_out():
    cfg = _make_cfg(probe_timeout_seconds=0.1)
    http_error = urllib.error.HTTPError(
        url="http://localhost:8000/admin/login/",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=None,
    )

    with (
        patch.object(browser.urllib.request, "urlopen", side_effect=http_error) as urlopen,
        patch.object(browser, "open_browser") as open_browser,
        patch.object(browser.time, "sleep"),
    ):
        browser.wait_for_http(cfg)

    assert urlopen.call_count >= 1
    open_browser.assert_not_called()


def test_wait_for_http_retries_on_503_then_succeeds():
    cfg = _make_cfg(probe_timeout_seconds=5.0)
    http_error = urllib.error.HTTPError(
        url="http://localhost:8000/admin/login/",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=None,
    )
    success_response = MagicMock()
    success_response.status = 200

    with (
        patch.object(
            browser.urllib.request,
            "urlopen",
            side_effect=[http_error, http_error, success_response],
        ) as urlopen,
        patch.object(browser, "open_browser") as open_browser,
        patch.object(browser.time, "sleep"),
    ):
        browser.wait_for_http(cfg)

    assert urlopen.call_count == 3
    open_browser.assert_called_once_with(cfg)


def test_wait_for_http_times_out_on_connection_refused():
    cfg = _make_cfg(probe_timeout_seconds=0.1)

    with (
        patch.object(
            browser.urllib.request,
            "urlopen",
            side_effect=ConnectionRefusedError("refused"),
        ) as urlopen,
        patch.object(browser, "open_browser") as open_browser,
        patch.object(browser.time, "sleep"),
    ):
        browser.wait_for_http(cfg)

    assert urlopen.call_count >= 1
    open_browser.assert_not_called()


# ---------------------------------------------------------------------------
# Autologin URL probe / banner
# ---------------------------------------------------------------------------


def _http_error(code: int, url: str = "http://localhost:8000/dev-helpers/autologin/"):
    return urllib.error.HTTPError(url=url, code=code, msg="boom", hdrs=None, fp=None)


def test_open_browser_opens_autologin_url_when_wired():
    """When the autologin URL responds with anything other than 404, open it."""
    cfg = _make_cfg(autologin_enabled=True)
    response = MagicMock()
    response.status = 405  # require_http_methods(["GET"]) rejects HEAD with 405

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.tokens, "current_token", return_value="TKN"),
        patch.object(browser.urllib.request, "urlopen", return_value=response) as urlopen,
        patch.object(browser.webbrowser, "open") as wb_open,
    ):
        browser.open_browser(cfg)

    assert urlopen.called
    wb_open.assert_called_once_with("http://localhost:8000/dev-helpers/autologin/?token=TKN")


def test_open_browser_opens_root_and_warns_when_autologin_returns_404(capsys):
    cfg = _make_cfg(autologin_enabled=True)

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.tokens, "current_token", return_value="TKN"),
        patch.object(browser.urllib.request, "urlopen", side_effect=_http_error(404)),
        patch.object(browser.webbrowser, "open") as wb_open,
    ):
        browser.open_browser(cfg)

    wb_open.assert_called_once_with("http://localhost:8000/")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "django-dev-helpers" in combined
    assert "autologin" in combined.lower()
    assert "urls.py" in combined or "urlpatterns" in combined or "autologin_urlpatterns" in combined


def test_open_browser_opens_root_when_autologin_disabled():
    """When autologin is disabled, no probe is needed and we go straight to /."""
    cfg = _make_cfg(autologin_enabled=False)

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.urllib.request, "urlopen") as urlopen,
        patch.object(browser.webbrowser, "open") as wb_open,
    ):
        browser.open_browser(cfg)

    urlopen.assert_not_called()
    wb_open.assert_called_once_with("http://localhost:8000/")


def test_open_browser_honors_explicit_url_path_without_probing():
    """If the user explicitly set browser_open.url_path, we don't probe autologin."""
    cfg = _make_cfg(autologin_enabled=True, browser_url_path="/admin/")

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.urllib.request, "urlopen") as urlopen,
        patch.object(browser.webbrowser, "open") as wb_open,
    ):
        browser.open_browser(cfg)

    urlopen.assert_not_called()
    wb_open.assert_called_once_with("http://localhost:8000/admin/")


def test_open_browser_opens_autologin_when_probe_connection_errors():
    """A connection error during the probe is treated as 'unknown' -- behave as before."""
    cfg = _make_cfg(autologin_enabled=True)

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.tokens, "current_token", return_value="TKN"),
        patch.object(
            browser.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("nope"),
        ),
        patch.object(browser.webbrowser, "open") as wb_open,
    ):
        browser.open_browser(cfg)

    wb_open.assert_called_once_with("http://localhost:8000/dev-helpers/autologin/?token=TKN")


def test_open_browser_probe_uses_head_method():
    """We want HEAD because the autologin view has @require_http_methods(['GET']).
    HEAD on a wired URL returns 405 (URL exists, method not allowed); HEAD on an
    unmounted URL returns 404. Using HEAD therefore avoids triggering a real
    autologin side effect during the probe."""
    cfg = _make_cfg(autologin_enabled=True)
    response = MagicMock()
    response.status = 405

    with (
        patch.object(browser.dotfiles, "discover_bind_host", return_value="localhost"),
        patch.object(browser.dotfiles, "discover_port", return_value="8000"),
        patch.object(browser.tokens, "current_token", return_value="TKN"),
        patch.object(browser.urllib.request, "urlopen", return_value=response) as urlopen,
        patch.object(browser.webbrowser, "open"),
    ):
        browser.open_browser(cfg)

    assert urlopen.call_count == 1
    request_arg = urlopen.call_args[0][0]
    assert request_arg.get_method() == "HEAD"
