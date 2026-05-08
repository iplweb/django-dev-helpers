from __future__ import annotations

import logging
import shlex
import sys

logger = logging.getLogger(__name__)

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


def render_template(cfg) -> str:
    from . import dotfiles, project_root

    root = project_root.resolve_project_root(cfg)
    port = dotfiles.discover_port()
    raw_host = dotfiles.discover_bind_host()
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
    db_user = db_info.get("db_user", "") or ""
    db_password = db_info.get("db_password", "") or ""
    db_name = db_info.get("db_name", "") or ""

    show_creds = getattr(cfg.agent_help, "show_db_credentials", True)

    db_user_or_redacted = db_user if show_creds else "<redacted>"

    quoted_user = shlex.quote(db_user) if db_user else ""
    quoted_name = shlex.quote(db_name) if db_name else ""

    if show_creds and db_password:
        quoted_password = shlex.quote(db_password)
        pg_command_with_or_without_password = (
            f'PGPASSWORD={quoted_password} psql -h "$PG_HOST" -p "$PG_PORT" -U {quoted_user} -d {quoted_name}'
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

    template_str = cfg.agent_help.template if cfg.agent_help.template is not None else _DEFAULT_TEMPLATE

    return template_str.format(
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
