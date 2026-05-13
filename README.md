# django-dev-helpers

[![PyPI](https://img.shields.io/pypi/v/django-dev-helpers.svg)](https://pypi.org/project/django-dev-helpers/)
[![CI](https://github.com/iplweb/django-dev-helpers/actions/workflows/ci.yml/badge.svg)](https://github.com/iplweb/django-dev-helpers/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1%20%7C%205.2%20%7C%206.0-green)](https://www.djangoproject.com/)

Dev-time conveniences for Django projects: autologin endpoint, dotfiles for LLM coding agents, agent help prompt, and gitignore self-check.

## Features

- **Autologin endpoint** — one URL logs in a user via token, no interactive login needed
- **Auth-state query toggles** — `?__autologin__=tmp_off|logout|log_in` on *any* URL to flip auth state in the browser without leaving the page
- **Dotfiles** — `.dev_helpers_token`, `.dev_helpers_port`, `.dev_helpers_pg_*`, `.dev_helpers_redis_*` written to project root for easy `cat` by LLM agents
- **Agent help prompt** — copy-pasteable curl/psql/redis-cli commands printed at startup
- **Gitignore self-check** — warns if dotfiles are not in `.gitignore`
- **Browser auto-open** — opens autologin URL in browser after server starts
- **`ALLOWED_HOSTS` auto-injection** — when started by [`run-site`](https://github.com/iplweb/django-run-site) `--bind 0.0.0.0`, unions the discovered LAN hostnames/IPs into `settings.ALLOWED_HOSTS` so other devices on the network can reach the dev server without per-project edits
- **Production-safe** — default-off, requires explicit `enabled=True`, raises on `DEBUG=False`

## Installation

```bash
pip install django-dev-helpers
# or
uv add django-dev-helpers --group dev
```

## Quick Start

1. Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_dev_helpers",
]
```

2. Enable in settings:

```python
DJANGO_DEV_HELPERS = {"enabled": True}
```

Or via environment variable:
```bash
DJANGO_DEV_HELPERS_ENABLED=1 python manage.py runserver
```

That's it — autologin is wired automatically. On startup, the package will:
- Generate an autologin token
- Auto-install `AutologinMiddleware` into `MIDDLEWARE` so the autologin URL works
  without `urls.py` changes (refuses to load if `DEBUG=False`)
- Write dotfiles to your project root
- Check `.gitignore`
- Print agent help after first request
- Open browser at the autologin URL (falls back to `/` with a banner if the URL
  is somehow not wired)

If you'd rather wire the URL by hand (e.g. to mount it under a prefix), set
`{"autologin": {"middleware_autoinstall": False}}` and add to `urls.py`:

```python
from django_dev_helpers.urls import autologin_urlpatterns

urlpatterns = [
    *autologin_urlpatterns(),
    # ... your other URLs
]
```

## Usage

### Autologin URL (token-based)

```bash
T=$(cat .dev_helpers_token)
curl -L "http://localhost:8000/__autologin__/?token=$T"
```

### Auth-state toggles (browser-friendly)

Once `AutologinMiddleware` is wired (the default), every request is scanned for
a toggle query parameter. Drop it onto any URL — the middleware handles it
before URL resolution.

| URL on any view | Effect |
|---|---|
| `https://localhost:8000/some/page/?__autologin__=tmp_off` | Render **this one request** with `request.user = AnonymousUser`. Session unchanged — the next plain request is logged in again. Toggle param stripped from `request.GET` before the view sees it. |
| `https://localhost:8000/some/page/?__autologin__=logout` | `django.contrib.auth.logout(request)` — ends the session. 302 to the same path with the toggle stripped; other query parameters preserved. |
| `https://localhost:8000/some/page/?__autologin__=log_in` (or `login`) | Log in the configured user (`autologin.user_lookup_field` / `user_lookup_value`). 302 to the cleaned URL. No URL token required — the localhost host allowlist is the trust signal. |

Unknown values pass through silently (likely typos). Off-host requests pass
through identically — the toggles do not announce their existence to
unauthorized hosts.

Rename the parameter via `autologin.query_param`, or set it to `""` / `None`
to disable the toggle layer while keeping the path-based `/__autologin__/`
URL working. Full details and threat model:
[docs/autologin.md](docs/autologin.md#toggle-query-parameters).

### Middleware ordering

`AutologinMiddleware` is auto-appended at the **end** of `settings.MIDDLEWARE`
during `AppConfig.ready()`. That works because the toggles need
`SessionMiddleware`, `AuthenticationMiddleware`, and `MessageMiddleware` to
have already run by the time we look at the request — sessions for
`logout`/`log_in`, `request.user` set up so `tmp_off` can override it, and
`request._messages` for the path-based view's `flash_message`.

If you install the middleware **manually** (with
`autologin.middleware_autoinstall=False`), place it **after** those three:

```python
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # ... your other middleware ...
    "django_dev_helpers.middleware.AutologinMiddleware",
]
```

Putting it before `SessionMiddleware`/`AuthenticationMiddleware`/`MessageMiddleware` will break `logout`, `log_in`, and `flash_message` respectively.

### Auto-injected `ALLOWED_HOSTS` (with `run-site`)

When the dev server is started via
[`run-site`](https://github.com/iplweb/django-run-site) >= 0.13.0 with
a non-loopback bind (e.g. `run-site run --bind 0.0.0.0`),
`run-site` discovers the machine's mDNS hostname and primary LAN IP
and exports them under `DEV_HELPERS_ALLOWED_HOSTS`. At
`AppConfig.ready()`, `django-dev-helpers` reads that env var and
unions the entries into `settings.ALLOWED_HOSTS`.

This means a phone on the same Wi‑Fi can hit
`http://your-mac.local:8000/` without you touching `settings.py` —
even when the project hard-codes `ALLOWED_HOSTS = ['localhost']`.

Behaviour:

- Idempotent — safe under runserver autoreload, no duplicate entries.
- Gated by `is_active()` (i.e. `DJANGO_DEV_HELPERS_ENABLED=1`) — the
  env var is ignored unless the helper is fully activated, so a
  leftover var in production cannot mutate `ALLOWED_HOSTS`.
- No-op when `settings.ALLOWED_HOSTS` already contains `*` (your
  setting takes precedence — adding more entries accomplishes nothing).
- No-op when the env var is unset (default `--bind 127.0.0.1` runs).

You can also set `DEV_HELPERS_ALLOWED_HOSTS=host1,host2,...` manually
when running outside `run-site` if you want the same convenience.

### Management Commands

```bash
python manage.py dev_helpers_doctor          # Full diagnostic
python manage.py dev_helpers_print_help      # Print agent prompt
python manage.py dev_helpers_check_gitignore # Check .gitignore entries (read-only)
python manage.py dev_helpers_fix_gitignore   # Add missing .gitignore entries (idempotent)
```

`dev_helpers_fix_gitignore` is the one you want when you see the
*"missing entries from .gitignore"* warning on startup — it appends the
missing dotfile names (and only those) without reordering existing
rules. Pass `--dry-run` to preview. See
[docs/configuration.md#gitignore](docs/configuration.md#gitignore) for
the full contract.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Configuration reference](docs/configuration.md)
- [Autologin endpoint](docs/autologin.md)
- [Dotfiles + lookup chain](docs/dotfiles.md)
- [Agent help / prompt](docs/agent-help.md)
- [Standalone usage](docs/standalone-usage.md)
- [Using with django-run-site](docs/with-django-run-site.md)
- [Security](docs/security.md)
- [Original design spec (frozen)](docs/design/spec-v0.1.md) — for design rationale

## Configuration

All configuration via `settings.DJANGO_DEV_HELPERS` dict. See [configuration docs](docs/configuration.md) for full reference.

```python
DJANGO_DEV_HELPERS = {
    "enabled": True,
    "autologin": {
        "user_lookup_field": "username",
        "user_lookup_value": "admin",
        "url_path": "__autologin__/",
        "redirect_to": "/",
        # Middleware that handles the autologin URL + auth-state toggles.
        # Auto-appended to settings.MIDDLEWARE; refuses to load when DEBUG=False.
        "middleware_autoinstall": True,
        # Name of the query toggle (?__autologin__=tmp_off|logout|log_in).
        # Set to "" or None to disable the toggle layer.
        "query_param": "__autologin__",
    },
    "dotfiles": {
        "enabled": True,
    },
    "agent_help": {
        "auto_print": True,
    },
    "browser_open": {
        "enabled": True,
    },
    "gitignore": {
        "mode": "warn",  # warn | auto-add | error | off
    },
}
```

## Security

This package exposes an autologin backdoor for development. It is **always off by default**:

- `enabled` must be explicitly set to `True` (via settings or env var)
- Raises `ImproperlyConfigured` if `DEBUG=False` and serving HTTP
- Autologin view verifies token via `hmac.compare_digest` (timing-safe)
- Only accepts requests from localhost/127.0.0.1 by default
- Returns 404 (not 403/401) on any failure — endpoint appears non-existent

**Never install this package in production.** Add it only to dev dependencies.

## Requirements

- Python >= 3.11
- Django >= 4.2

## Supported versions

Combinations exercised on every push by the CI matrix
(`.github/workflows/ci.yml`):

|             | Python 3.11 | Python 3.12 | Python 3.13 |
|-------------|:-----------:|:-----------:|:-----------:|
| Django 4.2  |      ✓      |      ✓      |      ✓      |
| Django 5.0  |      ✓      |      ✓      |      ✓      |
| Django 5.1  |      ✓      |      ✓      |      ✓      |
| Django 5.2  |      ✓      |      ✓      |      ✓      |
| Django 6.0  |      —      |      ✓      |      ✓      |

Django 6.0 requires Python ≥ 3.12, so the `(3.11, 6.0)` cell is excluded
from CI.

## License

MIT
