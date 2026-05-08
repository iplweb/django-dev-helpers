# django-dev-helpers

[![CI](https://github.com/mpasternak/django-dev-helpers/actions/workflows/ci.yml/badge.svg)](https://github.com/mpasternak/django-dev-helpers/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1%20%7C%205.2-green)](https://www.djangoproject.com/)

Dev-time conveniences for Django projects: autologin endpoint, dotfiles for LLM coding agents, agent help prompt, and gitignore self-check.

## Features

- **Autologin endpoint** — one URL logs in a user via token, no interactive login needed
- **Dotfiles** — `.dev_helpers_token`, `.dev_helpers_port`, `.dev_helpers_pg_*`, `.dev_helpers_redis_*` written to project root for easy `cat` by LLM agents
- **Agent help prompt** — copy-pasteable curl/psql/redis-cli commands printed at startup
- **Gitignore self-check** — warns if dotfiles are not in `.gitignore`
- **Browser auto-open** — opens autologin URL in browser after server starts
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

3. Add URL patterns in your `urls.py`:

```python
from django_dev_helpers.urls import autologin_urlpatterns

urlpatterns = [
    *autologin_urlpatterns(),
    # ... your other URLs
]
```

That's it. On startup, the package will:
- Generate an autologin token
- Write dotfiles to your project root
- Check `.gitignore`
- Print agent help after first request
- Open browser with autologin URL

## Usage

### Autologin

```bash
T=$(cat .dev_helpers_token)
curl -L "http://localhost:8000/__autologin__/?token=$T"
```

### Management Commands

```bash
python manage.py dev_helpers_doctor          # Full diagnostic
python manage.py dev_helpers_print_help      # Print agent prompt
python manage.py dev_helpers_check_gitignore # Check .gitignore entries
```

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

## License

MIT
