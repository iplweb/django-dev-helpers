import json

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from django_dev_helpers.conf import reset_config
from django_dev_helpers.middleware import LiveReloadMiddleware

rf = RequestFactory()


def _html_view(request):
    return HttpResponse("<html><body>hi</body></html>", content_type="text/html")


def test_sse_path_intercepted():
    mw = LiveReloadMiddleware(_html_view)
    resp = mw(rf.get("/__dev_reload__/"))
    assert resp["Content-Type"] == "text/event-stream"


def test_clients_path_returns_count():
    mw = LiveReloadMiddleware(_html_view)
    resp = mw(rf.get("/__dev_reload__/clients"))
    assert resp.status_code == 200
    assert "count" in json.loads(resp.content)


def test_script_injected_into_html():
    mw = LiveReloadMiddleware(_html_view)
    resp = mw(rf.get("/"))
    assert b"EventSource" in resp.content


def test_content_length_updated_after_injection():
    def view(request):
        resp = HttpResponse("<html><body>hi</body></html>", content_type="text/html")
        resp["Content-Length"] = str(len(resp.content))
        return resp

    mw = LiveReloadMiddleware(view)
    resp = mw(rf.get("/"))
    assert int(resp["Content-Length"]) == len(resp.content)


def test_no_injection_for_non_html():
    def view(request):
        return HttpResponse('{"a": 1}', content_type="application/json")

    mw = LiveReloadMiddleware(view)
    resp = mw(rf.get("/"))
    assert b"EventSource" not in resp.content


@override_settings(DEBUG=False)
def test_no_injection_when_debug_off():
    reset_config()
    mw = LiveReloadMiddleware(_html_view)
    resp = mw(rf.get("/"))
    assert b"EventSource" not in resp.content


@override_settings(DJANGO_DEV_HELPERS={"enabled": True, "live_reload": {"enabled": False}})
def test_disabled_config_skips_everything():
    reset_config()
    mw = LiveReloadMiddleware(_html_view)
    assert b"EventSource" not in mw(rf.get("/")).content
    # endpoint falls through to the wrapped view, not intercepted
    assert mw(rf.get("/__dev_reload__/")).content == b"<html><body>hi</body></html>"
