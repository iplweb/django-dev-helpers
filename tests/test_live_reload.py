import json

from django_dev_helpers import live_reload


def test_boot_id_is_stable_nonempty():
    assert isinstance(live_reload.BOOT_ID, str)
    assert live_reload.BOOT_ID
    assert live_reload.BOOT_ID == live_reload.BOOT_ID


def test_registry_tracks_connections():
    live_reload._reset()
    assert live_reload.count() == 0
    a = live_reload.register()
    b = live_reload.register()
    assert live_reload.count() == 2
    live_reload.unregister(a)
    assert live_reload.count() == 1
    live_reload.unregister(b)
    assert live_reload.count() == 0


def test_unregister_unknown_is_noop():
    live_reload._reset()
    live_reload.unregister(999)
    assert live_reload.count() == 0


def test_inject_inserts_script_before_body():
    html = "<html><body>hi</body></html>"
    out = live_reload.inject(html)
    assert "EventSource" in out
    assert out.index("EventSource") < out.rindex("</body>")


def test_inject_noop_without_body():
    html = "<p>no body tag</p>"
    assert live_reload.inject(html) == html


def test_inject_uses_last_body_case_insensitive():
    html = "<BODY>x</BODY>"
    out = live_reload.inject(html)
    assert "EventSource" in out
    assert out.rindex("EventSource") < out.rindex("</BODY>")


def test_event_stream_first_chunk_has_boot_id_and_retry():
    live_reload._reset()
    live_reload._shutdown.clear()
    gen = live_reload.event_stream()
    first = next(gen).decode()
    assert "event: hello" in first
    assert "retry:" in first
    assert live_reload.BOOT_ID in first
    gen.close()


def test_event_stream_registers_and_unregisters():
    live_reload._reset()
    live_reload._shutdown.clear()
    gen = live_reload.event_stream()
    assert live_reload.count() == 0
    next(gen)
    assert live_reload.count() == 1
    gen.close()
    assert live_reload.count() == 0


def test_sse_response_headers():
    # Constructing the response does not start the generator, so no
    # connection is registered and there is nothing to clean up here.
    resp = live_reload.sse_response()
    assert resp["Content-Type"] == "text/event-stream"
    assert resp["Cache-Control"] == "no-cache"
    assert resp["X-Accel-Buffering"] == "no"


def test_clients_response_reports_count():
    live_reload._reset()
    resp = live_reload.clients_response()
    assert json.loads(resp.content) == {"count": 0}
    cid = live_reload.register()
    resp = live_reload.clients_response()
    assert json.loads(resp.content) == {"count": 1}
    live_reload.unregister(cid)
