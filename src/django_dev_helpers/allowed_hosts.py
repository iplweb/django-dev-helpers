"""Inject orchestrator-supplied hosts into ``settings.ALLOWED_HOSTS``.

When ``run-site --bind 0.0.0.0`` (or any non-loopback bind) starts the
dev server, it discovers reachable LAN hostnames and IPs and exports
them via the ``DEV_HELPERS_ALLOWED_HOSTS`` env-var contract. Without
this injection, hitting the dev server from a phone or another laptop
on the LAN would trip ``DisallowedHost``.

Safe in dev only — gated by :meth:`DevHelpersConfig.is_active` (which
requires ``DJANGO_DEV_HELPERS_ENABLED=1``), so a stray copy of the env
var in production has no effect unless the helper is also activated.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

ENV_VAR = "DEV_HELPERS_ALLOWED_HOSTS"


def inject_allowed_hosts() -> tuple[str, ...]:
    """Union ``DEV_HELPERS_ALLOWED_HOSTS`` into ``settings.ALLOWED_HOSTS``.

    Returns the tuple of hosts actually appended (may be empty if the env
    var is unset or every host is already present). The function is
    idempotent — calling it twice is harmless because the second pass
    sees the previous additions and skips them.

    Mutating ``settings.ALLOWED_HOSTS`` at startup is a well-trodden
    Django pattern (test runners, ``ALLOWED_HOSTS = ['*']`` shims,
    etc.). We do it from ``apps.ready()``, before any request is served,
    so ``HttpRequest.get_host()`` validation sees the merged list.

    A wildcard ``*`` already in the user's settings is respected: we
    leave the list alone in that case, since adding more entries
    accomplishes nothing.
    """

    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return ()

    incoming = tuple(host.strip() for host in raw.split(",") if host.strip())
    if not incoming:
        return ()

    from django.conf import settings

    current = list(getattr(settings, "ALLOWED_HOSTS", None) or [])
    if "*" in current:
        return ()

    existing = set(current)
    added: list[str] = []
    for host in incoming:
        if host in existing:
            continue
        existing.add(host)
        current.append(host)
        added.append(host)

    if not added:
        return ()

    settings.ALLOWED_HOSTS = current
    logger.debug(
        "django-dev-helpers: appended %s to ALLOWED_HOSTS from %s",
        added,
        ENV_VAR,
    )
    return tuple(added)
