import asyncio
import inspect
import io
import json

import pytest

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


def test_sync_event_stream_is_sync_async_event_stream_is_async():
    # WSGI runserver streams a sync iterator lazily; ASGI needs an async
    # generator so a disconnect/reload can cancel it. Wrong kind on either
    # host is the bug this split fixes.
    live_reload._reset()
    live_reload._shutdown.clear()
    assert inspect.isgenerator(live_reload.sync_event_stream())
    assert inspect.isasyncgen(live_reload.async_event_stream())


def test_sync_event_stream_first_chunk_and_registration():
    live_reload._reset()
    live_reload._shutdown.set()  # end after hello; skip the heartbeat loop
    try:
        gen = live_reload.sync_event_stream()
        assert live_reload.count() == 0
        first = next(gen).decode()
        assert "event: hello" in first
        assert "retry:" in first
        assert live_reload.BOOT_ID in first
        assert live_reload.count() == 1
        gen.close()
        assert live_reload.count() == 0
    finally:
        live_reload._shutdown.clear()


def test_async_event_stream_first_chunk_and_registration():
    live_reload._reset()
    live_reload._shutdown.clear()

    async def scenario():
        gen = live_reload.async_event_stream()
        assert live_reload.count() == 0
        first = (await gen.__anext__()).decode()
        assert "event: hello" in first
        assert "retry:" in first
        assert live_reload.BOOT_ID in first
        assert live_reload.count() == 1
        await gen.aclose()
        assert live_reload.count() == 0

    asyncio.run(scenario())


def test_async_event_stream_cancel_during_heartbeat_releases_connection_promptly():
    # The failure mode this fix targets: when the serving task is cancelled
    # mid-heartbeat (exactly what daphne does on client disconnect / autoreload
    # restart), the generator must run its finally and unregister immediately,
    # not block until the heartbeat wait elapses.
    live_reload._reset()
    live_reload._shutdown.clear()

    async def scenario():
        agen = live_reload.async_event_stream(heartbeat_interval=100)
        first = (await agen.__anext__()).decode()
        assert "event: hello" in first
        assert live_reload.count() == 1

        # This chunk parks in the 100s heartbeat wait. Cancelling the task
        # must interrupt it, run the finally, and drop the connection.
        task = asyncio.ensure_future(agen.__anext__())
        await asyncio.sleep(0.05)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert live_reload.count() == 0

    # wait_for's 5s ceiling turns a regression (blocking wait) into a fast
    # test failure instead of a 100s hang.
    asyncio.run(asyncio.wait_for(scenario(), timeout=5.0))


def test_sse_response_headers():
    # Constructing the response does not start the generator, so no
    # connection is registered and there is nothing to clean up here.
    resp = live_reload.sse_response()
    assert resp["Content-Type"] == "text/event-stream"
    assert resp["Cache-Control"] == "no-cache"
    assert resp["X-Accel-Buffering"] == "no"


def test_sse_response_picks_sync_stream_for_wsgi():
    # No request (or a WSGI request) → sync stream, which the WSGI dev server
    # streams lazily. Prove the hello frame comes through by plain iteration
    # (no async_to_sync materialisation, so no infinite buffering).
    live_reload._reset()
    live_reload._shutdown.set()  # end after hello; skip the heartbeat loop
    try:
        resp = live_reload.sse_response()
        assert resp.is_async is False
        chunks = list(resp)
        assert chunks, "expected at least the hello frame"
        first = chunks[0].decode()
        assert "event: hello" in first
        assert live_reload.BOOT_ID in first
    finally:
        live_reload._shutdown.clear()
    assert live_reload.count() == 0


def test_sse_response_picks_async_stream_for_asgi():
    # An ASGI request → async stream, so daphne can cancel it on disconnect.
    from django.core.handlers.asgi import ASGIRequest

    live_reload._reset()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/__dev_reload__/",
        "query_string": b"",
        "headers": [],
    }
    request = ASGIRequest(scope, body_file=io.BytesIO(b""))
    resp = live_reload.sse_response(request)
    assert resp.is_async is True


def test_asgi_disconnect_cancels_stream_and_releases_connection():
    # End-to-end over Django's real ASGI handler + the auto-installed
    # LiveReloadMiddleware: an http.disconnect must cancel the streaming task
    # and release the connection promptly — the exact chain daphne drives on
    # client disconnect / autoreload restart. With the old sync generator the
    # streaming worker thread could not be cancelled, so daphne waited out
    # application_close_timeout and force-killed it, stalling the reload.
    from django.core.asgi import get_asgi_application

    live_reload._reset()
    live_reload._shutdown.clear()
    app = get_asgi_application()

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/__dev_reload__/",
        "raw_path": b"/__dev_reload__/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }

    async def scenario():
        hello_sent = asyncio.Event()
        request_read = {"done": False}
        sent = []

        async def receive():
            if not request_read["done"]:
                request_read["done"] = True
                return {"type": "http.request", "body": b"", "more_body": False}
            # listen_for_disconnect(): hold until the hello frame is out, then
            # signal the client going away.
            await hello_sent.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                hello_sent.set()

        task = asyncio.ensure_future(app(scope, receive, send))

        await asyncio.wait_for(hello_sent.wait(), timeout=5)
        assert live_reload.count() == 1  # connection registered, hello streamed

        # The disconnect is now deliverable; the handler must cancel the
        # stream, run the generator's finally, and finish.
        await asyncio.wait_for(task, timeout=5)
        assert live_reload.count() == 0

        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        assert b"event: hello" in body
        assert live_reload.BOOT_ID.encode() in body

    asyncio.run(asyncio.wait_for(scenario(), timeout=15))


def test_clients_response_reports_count():
    live_reload._reset()
    resp = live_reload.clients_response()
    assert json.loads(resp.content) == {"count": 0}
    cid = live_reload.register()
    resp = live_reload.clients_response()
    assert json.loads(resp.content) == {"count": 1}
    live_reload.unregister(cid)
