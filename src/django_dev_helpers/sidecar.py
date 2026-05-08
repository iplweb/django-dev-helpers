"""Reader for the run-site orchestrator's `.run-site-config` sidecar file.

run-site writes a TOML file at the project root recording the runtime
endpoints (Postgres, Redis, web port) of the currently running stack.
Reading the sidecar lets dev-helpers pick up endpoint info without
parsing settings.DATABASES or relying on a partial DEV_HELPERS_* env
contract.

Lookup order in conf is: callable > env > sidecar > settings.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SIDECAR_FILENAME = ".run-site-config"


def sidecar_path(project_root: Path) -> Path:
    return (project_root / SIDECAR_FILENAME).resolve()


def read_sidecar(project_root: Path) -> dict[str, Any] | None:
    """Load the TOML sidecar at <project_root>/.run-site-config.

    Returns the parsed dict, or None if the file is absent or malformed.
    Never raises — a broken sidecar must not break Django bootstrap.
    """
    path = sidecar_path(project_root)
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError):
        logger.warning("django-dev-helpers: failed to read sidecar at %s", path, exc_info=True)
        return None


def extract_endpoints(data: dict[str, Any]) -> dict[str, Any]:
    """Pull the keys dev-helpers cares about from the parsed sidecar.

    Returned keys (any subset, missing keys are simply absent):
      pg_host, pg_port, db_name, db_user, db_password,
      redis_host, redis_port, web_host, web_port.
    """
    out: dict[str, Any] = {}

    pg = data.get("postgres") or {}
    if pg.get("host"):
        out["pg_host"] = str(pg["host"])
    if pg.get("port") is not None:
        try:
            out["pg_port"] = int(pg["port"])
        except (TypeError, ValueError):
            logger.warning("django-dev-helpers: sidecar postgres.port is not an int: %r", pg.get("port"))
    if pg.get("db"):
        out["db_name"] = str(pg["db"])
    if pg.get("user"):
        out["db_user"] = str(pg["user"])
    if pg.get("password"):
        out["db_password"] = str(pg["password"])

    redis = data.get("redis") or {}
    if redis.get("host"):
        out["redis_host"] = str(redis["host"])
    if redis.get("port") is not None:
        try:
            out["redis_port"] = int(redis["port"])
        except (TypeError, ValueError):
            logger.warning("django-dev-helpers: sidecar redis.port is not an int: %r", redis.get("port"))

    web = data.get("web") or {}
    if web.get("host"):
        out["web_host"] = str(web["host"])
    if web.get("port") is not None:
        try:
            out["web_port"] = int(web["port"])
        except (TypeError, ValueError):
            logger.warning("django-dev-helpers: sidecar web.port is not an int: %r", web.get("port"))

    return out
