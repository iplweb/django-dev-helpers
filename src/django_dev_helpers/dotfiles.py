from __future__ import annotations

import atexit
import importlib
import logging
import os
import signal
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from django_dev_helpers import project_root, tokens
from django_dev_helpers import sidecar as sidecar_module

logger = logging.getLogger(__name__)

DEFAULT_DOTFILE_MODE = 0o644

_written_files: list[Path] = []
_cleanup_registered = False
_cleanup_done = False


def discover_port() -> str | None:
    env_port = os.environ.get("DEV_HELPERS_PORT")
    if env_port:
        return env_port
    argv = sys.argv
    for i, arg in enumerate(argv):
        if arg == "runserver":
            if i + 1 < len(argv):
                addr = argv[i + 1]
                if ":" in addr:
                    return addr.rsplit(":", 1)[-1]
                return addr
            return "8000"
    return None


def discover_bind_host() -> str:
    argv = sys.argv
    for i, arg in enumerate(argv):
        if arg == "runserver":
            if i + 1 < len(argv):
                addr = argv[i + 1]
                if ":" not in addr and addr.isdigit():
                    return "localhost"
                if addr == "::":
                    return "localhost"
                host = addr.rsplit(":", 1)[0] if ":" in addr else addr
                if host in ("0.0.0.0", "::", ""):
                    return "localhost"
                return host
            return "localhost"
    return "localhost"


def _resolve_via_callable(cfg) -> dict:
    spec = cfg.lookup.callable
    if not spec:
        return {}
    if ":" not in spec:
        logger.warning("django-dev-helpers: lookup.callable must be 'module.path:attr', got %r", spec)
        return {}
    module_path, attr = spec.split(":", 1)
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, attr)
    except (ImportError, AttributeError):
        logger.exception("django-dev-helpers: could not load lookup.callable %r", spec)
        return {}
    try:
        result = func(cfg)
    except Exception:
        logger.exception("django-dev-helpers: lookup.callable %r raised", spec)
        return {}
    if not isinstance(result, dict):
        logger.warning("django-dev-helpers: lookup.callable %r returned %r, expected dict", spec, type(result))
        return {}
    return result


def _resolve_via_env() -> dict:
    info: dict = {}
    string_keys = [
        ("DEV_HELPERS_DB_HOST", "pg_host"),
        ("DEV_HELPERS_DB_USER", "db_user"),
        ("DEV_HELPERS_DB_PASSWORD", "db_password"),
        ("DEV_HELPERS_DB_NAME", "db_name"),
        ("DEV_HELPERS_REDIS_HOST", "redis_host"),
    ]
    for env_key, info_key in string_keys:
        value = os.environ.get(env_key)
        if value:
            info[info_key] = value

    int_keys = [
        ("DEV_HELPERS_DB_PORT", "pg_port"),
        ("DEV_HELPERS_REDIS_PORT", "redis_port"),
    ]
    for env_key, info_key in int_keys:
        value = os.environ.get(env_key)
        if value:
            try:
                info[info_key] = int(value)
            except ValueError:
                logger.warning("django-dev-helpers: %s=%r is not an int, ignoring", env_key, value)
    return info


def _resolve_via_sidecar(cfg) -> dict:
    root = project_root.resolve_project_root(cfg)
    data = sidecar_module.read_sidecar(root)
    if data is None:
        return {}
    return sidecar_module.extract_endpoints(data)


def _resolve_via_settings() -> dict:
    info: dict = {}
    try:
        from django.conf import settings

        db = settings.DATABASES.get("default", {})
    except (AttributeError, KeyError):
        db = {}
    if db.get("HOST"):
        info["pg_host"] = str(db["HOST"])
    if db.get("PORT"):
        try:
            info["pg_port"] = int(db["PORT"])
        except (TypeError, ValueError):
            logger.warning("django-dev-helpers: DATABASES['default']['PORT']=%r is not an int", db.get("PORT"))
    if db.get("USER"):
        info["db_user"] = db["USER"]
    if db.get("PASSWORD"):
        info["db_password"] = db["PASSWORD"]
    if db.get("NAME"):
        info["db_name"] = db["NAME"]

    try:
        from django.conf import settings

        location = settings.CACHES.get("default", {}).get("LOCATION", "")
    except (AttributeError, KeyError):
        location = ""
    if isinstance(location, (list, tuple)):
        location = location[0] if location else ""
    if location:
        parsed = urlparse(location)
        if parsed.hostname:
            info["redis_host"] = parsed.hostname
        if parsed.port:
            info["redis_port"] = parsed.port
    return info


def resolve_db_info(cfg) -> dict:
    """Resolve DB and Redis endpoint info using the configured lookup chain.

    Precedence:
      1. lookup.callable (if specified) — full primary
      2. env vars (DEV_HELPERS_*)        — when source in {"env", "auto"}
      3. sidecar (.run-site-config)      — when source in {"sidecar", "auto"}
      4. settings.DATABASES + CACHES     — when source in {"settings", "auto"}

    Each later source only fills keys missing from earlier sources.
    """
    info: dict = {}

    for k, v in _resolve_via_callable(cfg).items():
        info.setdefault(k, v)

    source = cfg.lookup.source
    if source in ("env", "auto"):
        for k, v in _resolve_via_env().items():
            info.setdefault(k, v)
    if source in ("sidecar", "auto"):
        for k, v in _resolve_via_sidecar(cfg).items():
            info.setdefault(k, v)
    if source in ("settings", "auto"):
        for k, v in _resolve_via_settings().items():
            info.setdefault(k, v)

    return info


def resolve_pg_endpoint(cfg) -> tuple[str, int] | None:
    info = resolve_db_info(cfg)
    host = info.get("pg_host")
    port = info.get("pg_port")
    if host and port:
        return (str(host), int(port))
    return None


def resolve_redis_endpoint(cfg) -> tuple[str, int] | None:
    info = resolve_db_info(cfg)
    host = info.get("redis_host")
    port = info.get("redis_port")
    if host and port:
        return (str(host), int(port))
    return None


def _atomic_write(path: Path, content: str, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("django-dev-helpers: failed to remove temp file %s", tmp)
        raise


def write_all_dotfiles(cfg) -> None:
    global _written_files
    _written_files = []
    root = project_root.resolve_project_root(cfg)

    token = tokens.current_token()
    if token:
        token_path = root / cfg.dotfiles.token_filename
        _atomic_write(token_path, token, mode=cfg.dotfiles.token_chmod)
        _written_files.append(token_path)

    port = discover_port()
    if port:
        port_path = root / cfg.dotfiles.port_filename
        _atomic_write(port_path, port, mode=DEFAULT_DOTFILE_MODE)
        _written_files.append(port_path)

    db_info = resolve_db_info(cfg)

    pg_host = db_info.get("pg_host")
    if pg_host:
        pg_host_path = root / cfg.dotfiles.pg_host_filename
        _atomic_write(pg_host_path, str(pg_host), mode=DEFAULT_DOTFILE_MODE)
        _written_files.append(pg_host_path)

    pg_port = db_info.get("pg_port")
    if pg_port:
        pg_port_path = root / cfg.dotfiles.pg_port_filename
        _atomic_write(pg_port_path, str(pg_port), mode=DEFAULT_DOTFILE_MODE)
        _written_files.append(pg_port_path)

    redis_host = db_info.get("redis_host")
    if redis_host:
        redis_host_path = root / cfg.dotfiles.redis_host_filename
        _atomic_write(redis_host_path, str(redis_host), mode=DEFAULT_DOTFILE_MODE)
        _written_files.append(redis_host_path)

    redis_port = db_info.get("redis_port")
    if redis_port:
        redis_port_path = root / cfg.dotfiles.redis_port_filename
        _atomic_write(redis_port_path, str(redis_port), mode=DEFAULT_DOTFILE_MODE)
        _written_files.append(redis_port_path)


def remove_all_dotfiles(cfg) -> None:
    root = project_root.resolve_project_root(cfg)
    filenames = [
        cfg.dotfiles.token_filename,
        cfg.dotfiles.port_filename,
        cfg.dotfiles.pg_host_filename,
        cfg.dotfiles.pg_port_filename,
        cfg.dotfiles.redis_host_filename,
        cfg.dotfiles.redis_port_filename,
    ]
    for filename in filenames:
        try:
            (root / filename).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("django-dev-helpers: failed to remove dotfile %s", root / filename)


def register_cleanup(cfg) -> None:
    """Register atexit + SIGTERM handlers that remove dev-helpers dotfiles.

    Idempotent within a process: registering multiple times only installs
    a single atexit handler and a single SIGTERM chain.

    SIGTERM behavior: the previous handler (Django's runserver shutdown
    handler, if any) is preserved and called after our cleanup runs, so we
    don't break Django's graceful shutdown.
    """
    global _cleanup_registered
    if _cleanup_registered:
        return
    _cleanup_registered = True

    def _cleanup(*args, **kwargs):
        global _cleanup_done
        if _cleanup_done:
            return
        _cleanup_done = True
        try:
            remove_all_dotfiles(cfg)
        except Exception:
            logger.exception("django-dev-helpers: failed to clean up dotfiles")

    atexit.register(_cleanup)

    if os.name == "nt":
        return

    previous = signal.getsignal(signal.SIGTERM)

    def _sigterm_handler(signum, frame):
        _cleanup()
        if callable(previous):
            previous(signum, frame)
            return
        if previous == signal.SIG_DFL:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGTERM)
            return
        # SIG_IGN — caller asked to ignore SIGTERM, honour that.

    signal.signal(signal.SIGTERM, _sigterm_handler)
