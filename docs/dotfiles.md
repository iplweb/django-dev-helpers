# Dotfiles

Six small text files written to the project root so a coding agent can
`cat` them instead of parsing logs.

| File | Contents | Mode | Source |
|---|---|---|---|
| `.dev_helpers_token` | autologin token | 0600 | env or generated |
| `.dev_helpers_port` | runserver port | 0644 | env or `runserver` argv parse |
| `.dev_helpers_pg_host` | host for psql | 0644 | lookup chain |
| `.dev_helpers_pg_port` | port for psql | 0644 | lookup chain |
| `.dev_helpers_redis_host` | host for redis-cli | 0644 | lookup chain |
| `.dev_helpers_redis_port` | port for redis-cli | 0644 | lookup chain |

Each file holds one value, no trailing newline guarantee. Writes are atomic
(`mkstemp` + `os.replace`).

## Project root discovery

`dotfiles.directory = None` (default) → discovery in this order:

1. `DEV_HELPERS_PROJECT_ROOT` env var (set by `django-run-site`).
2. Walk up from `Path(settings.BASE_DIR)`: first ancestor (or `BASE_DIR`
   itself) containing one of `manage.py`, `pyproject.toml`, `runsite.toml`,
   `.git`.
3. Fallback: `Path(settings.BASE_DIR)`.

To force a directory, set `dotfiles.directory = "/abs/path"`.

## Lookup chain (DB/Redis)

`lookup.source = "auto"` (default) chains, in order — each step only fills
keys still missing:

1. **`lookup.callable`** — full primary; runs first when configured.
2. **Env vars** — `DEV_HELPERS_DB_HOST`, `DEV_HELPERS_DB_PORT`,
   `DEV_HELPERS_DB_USER`, `DEV_HELPERS_DB_PASSWORD`, `DEV_HELPERS_DB_NAME`,
   `DEV_HELPERS_REDIS_HOST`, `DEV_HELPERS_REDIS_PORT`.
3. **Sidecar** — `<project_root>/.run-site-config` (TOML written by
   `django-run-site` while a stack is running).
4. **Settings** — `settings.DATABASES["default"]` and
   `settings.CACHES["default"]["LOCATION"]` (parsed as a `redis://` URL).

To restrict to a single source, set `lookup.source` to `env`, `sidecar`, or
`settings`.

## Custom callable

```python
# myproject/dev_helpers_lookup.py
def resolve(cfg):
    return {
        "pg_host": "...",
        "pg_port": 5432,
        "db_user": "...",
        "db_password": "...",
        "db_name": "...",
        "redis_host": "...",
        "redis_port": 6379,
    }
```

```python
DJANGO_DEV_HELPERS = {
    "lookup": {"callable": "myproject.dev_helpers_lookup:resolve"},
}
```

Any keys you omit fall back to the rest of the chain.

## Cleanup

`atexit` removes all six dotfiles on normal interpreter exit. A `SIGTERM`
handler is also installed and chains to whatever handler was registered
before us (typically Django's runserver shutdown handler), so we don't
break Django's graceful shutdown. Cleanup is idempotent — running twice is
a no-op.

`SIGKILL` leaves dotfiles behind; the next run overwrites them.
