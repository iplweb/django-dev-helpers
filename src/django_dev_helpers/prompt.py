from __future__ import annotations

import logging
import shlex
import sys

logger = logging.getLogger(__name__)

# Used when ``cfg.agent_help.template`` is set to a user-provided string.
# In that mode we keep backward compatibility and just ``.format(**kwargs)``
# the template — no conditional rendering happens (the user owns the
# layout). For the *default* rendering, we ignore this constant and build
# the output dynamically in :func:`_build_default_prompt` so we can skip
# Postgres / Redis blocks for SQLite / cache-less projects.
_DEFAULT_TEMPLATE = """\
─── django-dev-helpers — agent prompt ───────────────────────────────

Server is up at: http://{host}:{port}

To fetch the authenticated home page (autologin):
  T=$(cat "{token_path}")
  PORT=$(cat "{port_path}")
  J=$(mktemp)
  curl -sc "$J" -L "http://{host}:$PORT/{autologin_path}?token=$T" >/dev/null
  curl -sb "$J" "http://{host}:$PORT/<path>"
  rm "$J"

To connect to PostgreSQL ({db_user_or_redacted}):
  PG_HOST=$(cat "{pg_host_path}")
  PG_PORT=$(cat "{pg_port_path}")
  {pg_command_with_or_without_password}

To connect to Redis:
  REDIS_HOST=$(cat "{redis_host_path}")
  REDIS_PORT=$(cat "{redis_port_path}")
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT"

──────────────────────────────────────────────────────────────────────"""


def _substitute_host(raw_host: str) -> str:
    if raw_host in ("0.0.0.0", "::"):
        return "localhost"
    return raw_host


def _detect_db_kind(db_info: dict) -> str:
    """Return one of ``'postgres'``, ``'sqlite'``, ``'unknown'``.

    Reads ``settings.DATABASES['default']['ENGINE']`` first; falls back
    to a heuristic on the resolved info dict when Django settings are
    unavailable (e.g. ``lookup.source = "env"`` against a non-Django
    consumer).
    """
    engine = ""
    try:
        from django.conf import settings

        engine = settings.DATABASES.get("default", {}).get("ENGINE", "") or ""
    except (AttributeError, KeyError):
        engine = ""
    if "sqlite" in engine:
        return "sqlite"
    if "postgres" in engine or "postgis" in engine:
        return "postgres"
    if db_info.get("pg_host") and db_info.get("pg_port"):
        return "postgres"
    return "unknown"


def _has_redis(db_info: dict) -> bool:
    """True iff we have actionable Redis endpoint info, OR the project
    declares a Redis cache backend in settings."""

    if db_info.get("redis_host"):
        return True
    try:
        from django.conf import settings

        backend = settings.CACHES.get("default", {}).get("BACKEND", "") or ""
        if "redis" in backend.lower():
            return True
    except (AttributeError, KeyError):
        pass
    return False


def _build_postgres_section(
    *,
    pg_host_path: str,
    pg_port_path: str,
    db_info: dict,
    show_creds: bool,
) -> list[str]:
    db_user = str(db_info.get("db_user", "") or "")
    db_password = str(db_info.get("db_password", "") or "")
    db_name = str(db_info.get("db_name", "") or "")

    db_user_or_redacted = db_user if show_creds else "<redacted>"
    quoted_user = shlex.quote(db_user) if db_user else "<user>"
    quoted_name = shlex.quote(db_name) if db_name else "<db>"

    if show_creds and db_password:
        quoted_password = shlex.quote(db_password)
        pg_command = (
            f'PGPASSWORD={quoted_password} psql -h "$PG_HOST" -p "$PG_PORT" '
            f"-U {quoted_user} -d {quoted_name}"
        )
    else:
        pg_command = (
            f'psql -h "$PG_HOST" -p "$PG_PORT"'
            f" -U {quoted_user} -d {quoted_name}"
            "  # password from env / .pgpass / settings"
        )

    return [
        "",
        f"To connect to PostgreSQL ({db_user_or_redacted}):",
        f'  PG_HOST=$(cat "{pg_host_path}")',
        f'  PG_PORT=$(cat "{pg_port_path}")',
        f"  {pg_command}",
    ]


def _build_sqlite_section(db_info: dict) -> list[str]:
    """SQLite databases are local files — no host/port, no credentials.
    Point the user (or coding agent) at the file path and show the
    one-liner to open it with the ``sqlite3`` CLI.

    ``show_db_credentials`` doesn't apply: the path isn't a secret. If
    the project really wants the path hidden, omit ``[django_dev_helpers]``
    from the install entirely.
    """

    db_name = str(db_info.get("db_name", "") or "")
    if not db_name:
        return []

    quoted = shlex.quote(db_name)
    if db_name == ":memory:":
        return [
            "",
            "Database: SQLite (in-memory).",
            "  No file on disk — open a Django shell to inspect ORM state:",
            "  python manage.py shell",
        ]
    return [
        "",
        f"To inspect the SQLite database ({db_name}):",
        f"  sqlite3 {quoted}",
        "",
        f"  # One-shot query: sqlite3 {quoted} 'SELECT * FROM auth_user LIMIT 5;'",
        "  # Exit the interactive shell with .quit",
    ]


def _build_redis_section(redis_host_path: str, redis_port_path: str) -> list[str]:
    return [
        "",
        "To connect to Redis:",
        f'  REDIS_HOST=$(cat "{redis_host_path}")',
        f'  REDIS_PORT=$(cat "{redis_port_path}")',
        '  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT"',
    ]


def _build_default_prompt(
    *,
    host: str,
    port: int | str | None,
    token_path: str,
    port_path: str,
    autologin_path: str,
    pg_host_path: str,
    pg_port_path: str,
    redis_host_path: str,
    redis_port_path: str,
    db_info: dict,
    show_creds: bool,
) -> str:
    # Port can be unknown when the prompt is rendered *before* the dev
    # server starts (e.g. ``manage.py run_site`` printing a suggestion
    # block while ``run-site`` itself hasn't picked a free port yet, so
    # ``DEV_HELPERS_PORT`` is unset, ``runserver`` is not in argv, and the
    # sidecar doesn't exist). Falling back to the ``$PORT`` placeholder
    # keeps the line copy-paste-correct: the very next lines source
    # ``PORT`` from the dotfile, so ``http://{host}:$PORT`` resolves
    # automatically.
    if port is None or port == "":
        header_url = f"http://{host}:$PORT (read $PORT from the dotfile below)"
    else:
        header_url = f"http://{host}:{port}"

    lines: list[str] = [
        "─── django-dev-helpers — agent prompt ───────────────────────────────",
        "",
        f"Server is up at: {header_url}",
        "",
        "To fetch the authenticated home page (autologin):",
        f'  T=$(cat "{token_path}")',
        f'  PORT=$(cat "{port_path}")',
        "  J=$(mktemp)",
        (
            f'  curl -sc "$J" -L "http://{host}:$PORT/{autologin_path}'
            '?token=$T" >/dev/null'
        ),
        f'  curl -sb "$J" "http://{host}:$PORT/<path>"',
        '  rm "$J"',
    ]

    db_kind = _detect_db_kind(db_info)
    if db_kind == "postgres":
        lines.extend(
            _build_postgres_section(
                pg_host_path=pg_host_path,
                pg_port_path=pg_port_path,
                db_info=db_info,
                show_creds=show_creds,
            )
        )
    elif db_kind == "sqlite":
        lines.extend(_build_sqlite_section(db_info))
    # 'unknown' → emit no DB section; we'd just be guessing.

    if _has_redis(db_info):
        lines.extend(_build_redis_section(redis_host_path, redis_port_path))

    lines.append("")
    lines.append("──────────────────────────────────────────────────────────────────────")
    return "\n".join(lines)


def render_template(cfg) -> str:
    from . import dotfiles, project_root

    root = project_root.resolve_project_root(cfg)
    port = dotfiles.discover_port(cfg)
    raw_host = dotfiles.discover_bind_host(cfg)
    host = _substitute_host(raw_host)

    if getattr(cfg.agent_help, "display_host", None):
        host = cfg.agent_help.display_host

    token_path = str(root / cfg.dotfiles.token_filename)
    port_path = str(root / cfg.dotfiles.port_filename)
    autologin_path = cfg.autologin.url_path

    pg_host_path = str(root / cfg.dotfiles.pg_host_filename)
    pg_port_path = str(root / cfg.dotfiles.pg_port_filename)
    redis_host_path = str(root / cfg.dotfiles.redis_host_filename)
    redis_port_path = str(root / cfg.dotfiles.redis_port_filename)

    db_info = dotfiles.resolve_db_info(cfg)
    show_creds = getattr(cfg.agent_help, "show_db_credentials", True)

    # User-supplied custom templates use the original ``.format()`` contract.
    # Building the format args here even when unused keeps that contract
    # stable; the default path ignores them and renders dynamically.
    db_user = str(db_info.get("db_user", "") or "")
    db_password = str(db_info.get("db_password", "") or "")
    db_name = str(db_info.get("db_name", "") or "")
    db_user_or_redacted = db_user if show_creds else "<redacted>"
    quoted_user = shlex.quote(db_user) if db_user else ""
    quoted_name = shlex.quote(db_name) if db_name else ""

    if show_creds and db_password:
        quoted_password = shlex.quote(db_password)
        pg_command_with_or_without_password = (
            f'PGPASSWORD={quoted_password} psql -h "$PG_HOST" -p "$PG_PORT" '
            f"-U {quoted_user} -d {quoted_name}"
        )
    else:
        pg_command_with_or_without_password = (
            f'psql -h "$PG_HOST" -p "$PG_PORT"'
            f" -U {quoted_user} -d {quoted_name}"
            "  # password from env / .pgpass / settings"
        )

    if show_creds:
        display_db_user = db_user
        display_db_password = db_password
        display_db_name = db_name
    else:
        display_db_user = "<redacted>"
        display_db_password = "<redacted>"
        display_db_name = "<redacted>"

    if cfg.agent_help.template is None:
        return _build_default_prompt(
            host=host,
            port=port,
            token_path=token_path,
            port_path=port_path,
            autologin_path=autologin_path,
            pg_host_path=pg_host_path,
            pg_port_path=pg_port_path,
            redis_host_path=redis_host_path,
            redis_port_path=redis_port_path,
            db_info=db_info,
            show_creds=show_creds,
        )

    return cfg.agent_help.template.format(
        host=host,
        port=port,
        token_path=token_path,
        port_path=port_path,
        autologin_path=autologin_path,
        pg_host_path=pg_host_path,
        pg_port_path=pg_port_path,
        redis_host_path=redis_host_path,
        redis_port_path=redis_port_path,
        db_user=display_db_user,
        db_password=display_db_password,
        db_name=display_db_name,
        db_user_or_redacted=db_user_or_redacted,
        pg_command_with_or_without_password=pg_command_with_or_without_password,
    )


_STATIC_HEADER = """\
{start_marker}
## Local dev server (django-dev-helpers)

When this project's Django dev server is running, runtime endpoint info is
written to dotfiles in the project root. If a dotfile referenced below is
missing, the dev server is not running.

### Authenticated request to the Django app

```bash
TOKEN=$(cat {token_filename})
PORT=$(cat {port_filename})
JAR=$(mktemp)
curl -sc "$JAR" -L "http://localhost:$PORT/{autologin_path}?token=$TOKEN" >/dev/null
curl -sb "$JAR" "http://localhost:$PORT/<path>"
rm "$JAR"
```
"""

_STATIC_POSTGRES = """\

### PostgreSQL

```bash
PG_HOST=$(cat {pg_host_filename})
PG_PORT=$(cat {pg_port_filename})
psql -h "$PG_HOST" -p "$PG_PORT" -U <user> -d <db>
```
"""

_STATIC_SQLITE = """\

### SQLite

The database is a local file at `{sqlite_path}`.

```bash
sqlite3 {sqlite_path_shell}
# One-shot query:
sqlite3 {sqlite_path_shell} 'SELECT * FROM auth_user LIMIT 5;'
```
"""

_STATIC_SQLITE_INMEMORY = """\

### SQLite (in-memory)

This project uses an in-memory SQLite database; there is no file on disk.
To inspect ORM state, run a Django shell:

```bash
python manage.py shell
```
"""

_STATIC_REDIS = """\

### Redis

```bash
REDIS_HOST=$(cat {redis_host_filename})
REDIS_PORT=$(cat {redis_port_filename})
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT"
```
"""


def derive_end_marker(start_marker: str) -> str:
    """Derive a paired end marker from the configured start marker.

    `<!-- django-dev-helpers:agent-help -->` -> `<!-- django-dev-helpers:agent-help-end -->`
    Falls back to appending `-end` if the marker doesn't match the HTML-comment shape.
    """
    suffix = " -->"
    if start_marker.endswith(suffix):
        body = start_marker[: -len(suffix)]
        return f"{body}-end{suffix}"
    return f"{start_marker}-end"


def render_static_agent_help_block(cfg) -> str:
    """Render the markdown block intended for AGENTS.md / CLAUDE.md.

    The block is *static* in the sense that it never embeds runtime values
    (host, port, db credentials). It only references dotfile filenames, so
    the markdown does not need regeneration when the server restarts on a
    different port or with different credentials.

    Sections are conditioned on the project's actual backing services:
    a SQLite-only project sees a ``### SQLite`` block (with the file path
    and a ``sqlite3`` invocation) and no ``### PostgreSQL`` / ``### Redis``
    sections; a project without Redis omits the Redis block.
    """
    from . import dotfiles

    autologin_path = cfg.autologin.url_path.lstrip("/")
    db_info = dotfiles.resolve_db_info(cfg)
    db_kind = _detect_db_kind(db_info)

    parts: list[str] = [
        _STATIC_HEADER.format(
            start_marker=cfg.claude_md.marker,
            token_filename=cfg.dotfiles.token_filename,
            port_filename=cfg.dotfiles.port_filename,
            autologin_path=autologin_path,
        )
    ]
    if db_kind == "postgres":
        parts.append(
            _STATIC_POSTGRES.format(
                pg_host_filename=cfg.dotfiles.pg_host_filename,
                pg_port_filename=cfg.dotfiles.pg_port_filename,
            )
        )
    elif db_kind == "sqlite":
        sqlite_path = str(db_info.get("db_name", "") or "")
        if sqlite_path == ":memory:":
            parts.append(_STATIC_SQLITE_INMEMORY)
        elif sqlite_path:
            parts.append(
                _STATIC_SQLITE.format(
                    sqlite_path=sqlite_path,
                    sqlite_path_shell=shlex.quote(sqlite_path),
                )
            )
    if _has_redis(db_info):
        parts.append(
            _STATIC_REDIS.format(
                redis_host_filename=cfg.dotfiles.redis_host_filename,
                redis_port_filename=cfg.dotfiles.redis_port_filename,
            )
        )
    parts.append(derive_end_marker(cfg.claude_md.marker) + "\n")
    return "".join(parts)


def register_first_request_print(cfg) -> None:
    from django.core.signals import request_started

    def _on_first_request(sender, **kwargs):
        try:
            rendered = render_template(cfg)
            sys.stdout.write(rendered + "\n")
            sys.stdout.flush()
        except Exception:
            logger.exception("django-dev-helpers: failed to render agent prompt")
        finally:
            request_started.disconnect(_on_first_request)

    request_started.connect(_on_first_request)
