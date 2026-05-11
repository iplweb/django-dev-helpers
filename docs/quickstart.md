# Quickstart

`django-dev-helpers` is a Django app that adds three things to a dev project: an
autologin URL for LLM agents, a set of dotfiles agents can `cat` to learn
ports/tokens, and a copy-paste agent prompt printed at startup.

## Install

```bash
uv add django-dev-helpers --group dev
# or
pip install django-dev-helpers
```

The package is dev-only — never ship it to production.

## Wire up

In `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "django_dev_helpers",
]

DJANGO_DEV_HELPERS = {"enabled": True}
```

…or activate via env var instead of settings:

```bash
DJANGO_DEV_HELPERS_ENABLED=1 python manage.py runserver
```

That's the whole setup — no `urls.py` changes are needed. On startup the
package auto-appends `django_dev_helpers.middleware.AutologinMiddleware` to
your `MIDDLEWARE` list, so the autologin URL works out of the box. The
middleware refuses to load when `DEBUG=False`, so an accidental production
deploy still can't expose the login backdoor.

If you'd rather wire the URL by hand (mount it under a prefix, etc.), set
`{"autologin": {"middleware_autoinstall": False}}` and add the pattern to
your `urls.py`:

```python
from django_dev_helpers.urls import autologin_urlpatterns

urlpatterns = [
    *autologin_urlpatterns(),
    path("admin/", admin.site.urls),
    # ...
]
```

## What happens on `runserver`

1. AppConfig generates an autologin token (or reuses one in
   `DEV_HELPERS_AUTOLOGIN_TOKEN`).
2. `AutologinMiddleware` is appended to `settings.MIDDLEWARE` so the
   autologin URL works without `urls.py` changes. Toggle off with
   `{"autologin": {"middleware_autoinstall": False}}`.
3. Dotfiles are written to the project root: `.dev_helpers_token`,
   `.dev_helpers_port`, `.dev_helpers_pg_host`, `.dev_helpers_pg_port`,
   `.dev_helpers_redis_host`, `.dev_helpers_redis_port`.
4. `.gitignore` is checked for those entries (warn-mode by default).
   If you see a warning about missing entries, fix it in one shot:
   `python manage.py dev_helpers_fix_gitignore` (idempotent, append-only).
   See [configuration.md#gitignore](configuration.md#gitignore) for the
   other modes (`auto-add`, `error`, `off`).
5. After the first request the agent help is printed to stdout.
6. The browser opens at the autologin URL once the server is reachable.
   If the autologin URL still returns 404 (e.g. you disabled both the
   middleware auto-install and the URL include), the browser-open code
   prints a banner explaining how to wire it and opens `/` instead.

## Verify

```bash
python manage.py dev_helpers_doctor
```

Should print all green ticks. See [security.md](security.md) for the production
kill switch and [autologin.md](autologin.md) for the URL contract.
