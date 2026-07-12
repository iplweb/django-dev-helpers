from __future__ import annotations

import asyncio
import json
import secrets
import threading
from collections.abc import AsyncIterator, Iterator

# One id per server process. Changes on every full restart AND on every
# autoreload child (a page reload on code change is a desirable side effect).
BOOT_ID = secrets.token_hex(8)

_lock = threading.Lock()
_connections: set[int] = set()
_next_id = 0
_shutdown = threading.Event()

# Inline client. Opens an EventSource; remembers the first boot_id it sees;
# reloads when a later "hello" reports a different boot_id. EventSource
# auto-reconnects on error, so a restart transparently re-attaches.
CLIENT_SCRIPT = (
    "<script>(function(){var b=null;"
    'var s=new EventSource("/__dev_reload__/");'
    's.addEventListener("hello",function(e){'
    "var i=JSON.parse(e.data).boot_id;"
    "if(b===null){b=i;}else if(i!==b){location.reload();}});})();</script>"
)


def register() -> int:
    global _next_id
    with _lock:
        _next_id += 1
        cid = _next_id
        _connections.add(cid)
        return cid


def unregister(cid: int) -> None:
    with _lock:
        _connections.discard(cid)


def count() -> int:
    with _lock:
        return len(_connections)


def _reset() -> None:
    """Test helper: clear the connection registry."""
    with _lock:
        _connections.clear()


def inject(html: str) -> str:
    """Insert CLIENT_SCRIPT immediately before the last </body> (case-
    insensitive). Returns html unchanged when there is no </body>."""
    idx = html.lower().rfind("</body>")
    if idx == -1:
        return html
    return html[:idx] + CLIENT_SCRIPT + html[idx:]


def request_shutdown() -> None:
    """Signal open event-stream generators to stop heartbeating.

    Secondary, explicit stop path. Under ASGI the primary mechanism is task
    cancellation: a client disconnect or an autoreload restart cancels the
    streaming task, which unwinds :func:`async_event_stream` immediately. This
    flag is the in-process nudge for callers that want open streams to wind
    down without a disconnect; it is honoured at the next heartbeat tick.
    """
    _shutdown.set()


def _hello_frame() -> bytes:
    payload = json.dumps({"boot_id": BOOT_ID})
    return f"retry: 1000\nevent: hello\ndata: {payload}\n\n".encode()


def sync_event_stream(heartbeat_interval: float = 2.0) -> Iterator[bytes]:
    """SSE generator for the classic WSGI ``runserver``.

    The WSGI dev server streams a *sync* iterator lazily, chunk by chunk, so
    this endless generator works there. Do NOT use it under ASGI: served over
    daphne a sync generator parks a worker thread in a blocking ``Event.wait``
    that the server cannot interrupt on disconnect, so it waits out
    ``application_close_timeout`` and force-kills the instance — stalling the
    reload. Use :func:`async_event_stream` for ASGI instead.
    """
    cid = register()
    try:
        yield _hello_frame()
        while not _shutdown.is_set():
            # wait() returns True the moment shutdown is set (stop), False on
            # timeout (send a heartbeat). Short waits keep runserver shutdown
            # from blocking on this thread for long.
            if _shutdown.wait(heartbeat_interval):
                break
            yield b": ping\n\n"
    finally:
        unregister(cid)


async def async_event_stream(heartbeat_interval: float = 2.0) -> AsyncIterator[bytes]:
    """SSE generator for ASGI servers (daphne / uvicorn).

    Async on purpose. Task cancellation on client disconnect or server
    autoreload propagates into the ``await asyncio.sleep`` below and runs the
    ``finally`` at once, so the connection is released immediately instead of
    daphne having to wait out ``application_close_timeout`` and force-kill it
    ("took too long to shut down and was killed"), which stalls the reload.
    Note: Django materialises a sync-served async iterator in full, so this
    endless generator must NOT be fed to a WSGI response — see
    :func:`sync_event_stream` and :func:`sse_response`.
    """
    cid = register()
    try:
        yield _hello_frame()
        while not _shutdown.is_set():
            await asyncio.sleep(heartbeat_interval)
            yield b": ping\n\n"
    finally:
        unregister(cid)


def _is_asgi_request(request) -> bool:
    """True when *request* is being served over ASGI (daphne/uvicorn).

    Django uses a distinct request class per handler; the async event stream
    is only safe when the response is streamed asynchronously.
    """
    if request is None:
        return False
    from django.core.handlers.asgi import ASGIRequest

    return isinstance(request, ASGIRequest)


def sse_response(request=None):
    """Build the live-reload SSE ``StreamingHttpResponse``.

    Picks the async generator under ASGI (cancelled cleanly on disconnect /
    reload) and the sync generator under WSGI (lazily streamed, never
    materialised). ``request`` is optional so callers that already know they
    are on WSGI can omit it and get the sync stream.
    """
    from django.http import StreamingHttpResponse

    stream = async_event_stream() if _is_asgi_request(request) else sync_event_stream()
    response = StreamingHttpResponse(stream, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def clients_response():
    from django.http import JsonResponse

    return JsonResponse({"count": count()})
