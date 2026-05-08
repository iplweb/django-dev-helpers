from __future__ import annotations

import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django_dev_helpers import browser


def _make_cfg(probe_timeout_seconds=0.1):
    return SimpleNamespace(
        browser_open=SimpleNamespace(
            enabled=True,
            url_path=None,
            probe_path="/admin/login/",
            probe_timeout_seconds=probe_timeout_seconds,
        ),
        autologin=SimpleNamespace(enabled=False, url_path="dev-helpers/autologin/"),
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
