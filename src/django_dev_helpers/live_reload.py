from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Iterator

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
    """Signal open event_stream generators to stop heartbeating promptly."""
    _shutdown.set()


def event_stream(heartbeat_interval: float = 2.0) -> Iterator[bytes]:
    cid = register()
    try:
        payload = json.dumps({"boot_id": BOOT_ID})
        yield f"retry: 1000\nevent: hello\ndata: {payload}\n\n".encode()
        while not _shutdown.is_set():
            # wait() returns True when shutdown is set (stop), False on
            # timeout (send a heartbeat). Short waits keep runserver
            # shutdown from blocking on this thread for long.
            if _shutdown.wait(heartbeat_interval):
                break
            yield b": ping\n\n"
    finally:
        unregister(cid)


def sse_response():
    from django.http import StreamingHttpResponse

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def clients_response():
    from django.http import JsonResponse

    return JsonResponse({"count": count()})
