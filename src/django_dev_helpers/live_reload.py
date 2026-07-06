from __future__ import annotations

import secrets
import threading

# One id per server process. Changes on every full restart AND on every
# autoreload child (a page reload on code change is a desirable side effect).
BOOT_ID = secrets.token_hex(8)

_lock = threading.Lock()
_connections: set[int] = set()
_next_id = 0

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
