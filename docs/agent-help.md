# Agent help / prompt template

A copy-paste-ready snippet of `curl`/`psql`/`redis-cli` commands using the
current dotfiles. Aimed at LLM coding agents (Claude Code, Aider, Cursor,
Codex) so they can do `WebFetch` on authenticated pages and connect to the
DB without asking the user for credentials each session.

## When it prints

`agent_help.auto_print = True` (default) hooks `request_started` and prints
the rendered template the first time Django serves any request. This
guarantees you only see the prompt after the server actually responds —
never during a startup race.

The print fires **once per dev session**; autoreload restarts of the same
process will not reprint.

You can also print on demand:

```bash
python manage.py dev_helpers_print_help
```

## Default template

```text
─── django-dev-helpers — agent prompt ───────────────────────────────

Server is up at: http://localhost:8000

To fetch the authenticated home page (autologin):
  T=$(cat ".../.dev_helpers_token")
  PORT=$(cat ".../.dev_helpers_port")
  J=$(mktemp)
  curl -sc "$J" -L "http://localhost:$PORT/__autologin__/?token=$T" >/dev/null
  curl -sb "$J" "http://localhost:$PORT/<path>"
  rm "$J"

To connect to PostgreSQL (myproject):
  PG_HOST=$(cat ".../.dev_helpers_pg_host")
  PG_PORT=$(cat ".../.dev_helpers_pg_port")
  PGPASSWORD=password psql -h "$PG_HOST" -p "$PG_PORT" -U myproject -d myproject

To connect to Redis:
  REDIS_HOST=$(cat ".../.dev_helpers_redis_host")
  REDIS_PORT=$(cat ".../.dev_helpers_redis_port")
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT"

──────────────────────────────────────────────────────────────────────
```

DB user/password/name are `shlex.quote`-d into the snippet, so passwords
containing `'`, `"`, `$`, spaces survive intact.

## Hiding credentials

`agent_help.show_db_credentials = False` swaps the password line for a
`# password from env / .pgpass / settings` comment and replaces the user
with `<redacted>`. Use this when the agent log goes somewhere other than
your terminal.

## Custom template

`agent_help.template = "..."` replaces the default. The string is passed
through `str.format` with these placeholders:

`host`, `port`, `token_path`, `port_path`, `autologin_path`,
`pg_host_path`, `pg_port_path`, `redis_host_path`, `redis_port_path`,
`db_user`, `db_password`, `db_name`, `db_user_or_redacted`,
`pg_command_with_or_without_password`.

Anything else with `{` in it (shell `${var}`, JSON, etc.) must be escaped
as `{{` / `}}` per `str.format` rules.

## Display host

Auto-substitution rewrites `0.0.0.0` and `::` to `localhost` (so the agent
can connect). Override with `agent_help.display_host = "myhost.local"` for
LAN testing.
