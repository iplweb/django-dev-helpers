# Using with `django-run-site`

[`django-run-site`](https://github.com/mpasternak/django-run-site) is the
companion CLI that orchestrates Postgres / Redis (testcontainers), runs
migrations, and starts `runserver`. `django-dev-helpers` is a Django app
that runs *inside* that runserver process. There is no code-level coupling
— they communicate via env vars and an optional sidecar file.

## What run-site sets

When run-site starts the runserver subprocess, it exports:

| Env var | Read by dev-helpers |
|---|---|
| `DJANGO_DEV_HELPERS_ENABLED=1` | activation |
| `DEV_HELPERS_AUTOLOGIN_TOKEN` | autologin token |
| `DEV_HELPERS_AUTOLOGIN_USERNAME` | autologin user (when not set in settings) |
| `DEV_HELPERS_PORT` | runserver port |
| `DEV_HELPERS_PROJECT_ROOT` | dotfile target dir |
| `DEV_HELPERS_DB_HOST` / `DB_PORT` / `DB_USER` / `DB_NAME` / `DB_PASSWORD` | DB endpoint |
| `DEV_HELPERS_REDIS_HOST` / `REDIS_PORT` | Redis endpoint |

## Sidecar file

run-site also writes `<project_root>/.run-site-config` (TOML) before the
runserver starts and removes it on clean shutdown. dev-helpers reads it as
a fallback in `lookup.source = "auto"`:

```toml
project_slug = "myproject"
generated_at = "..."

[web]
host = "127.0.0.1"
port = 49152

[postgres]
host = "127.0.0.1"
port = 49160
db = "myproject"
user = "myproject"
password = "..."

[redis]
host = "127.0.0.1"
port = 49161
db = 0

[celery]
enabled = false
```

Lookup precedence in `auto`: `lookup.callable` → env → sidecar → settings.
Each step only fills keys missing from earlier steps.

To force sidecar-only:

```python
DJANGO_DEV_HELPERS = {
    "lookup": {"source": "sidecar"},
}
```

`.run-site-config` is added to `.gitignore` by run-site itself; we don't
manage it.

## Browser-open ownership

| Mode | Tabs opened |
|---|---|
| run-site default + dev-helpers default | 2: homepage (run-site CLI) + autologin URL (dev-helpers) |
| run-site `--no-browser` + dev-helpers default | 1: autologin URL |
| run-site `--no-browser` + `browser_open.enabled=False` | 0 |

## Banner ownership

run-site prints its own banner (PG/Redis ports, dump info, Celery status)
at process start. dev-helpers prints the agent prompt after the first
request. They never collide.

## Migration from a hand-rolled `run_site` command

If you previously had a `bpp/management/commands/run_site.py` that wrote
`.run_site_token` / `.run_site_port`, the dev-helpers `dev_helpers_doctor`
now warns when it finds leftover `.run_site_*` files:

```bash
python manage.py dev_helpers_doctor
# ⚠ Legacy .run_site_* dotfiles: found 2 legacy file(s)…
```

Delete them — dev-helpers writes the canonical `.dev_helpers_*` set.
