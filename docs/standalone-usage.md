# Standalone usage (without django-run-site)

`django-dev-helpers` works as a plain Django app — no orchestrator, no
testcontainers, no extra dependencies beyond Django itself.

## With `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: myproject
      POSTGRES_DB: myproject
      POSTGRES_PASSWORD: password
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

```python
# settings.py
INSTALLED_APPS = [..., "django_dev_helpers"]
DJANGO_DEV_HELPERS = {"enabled": True}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "127.0.0.1",
        "PORT": 5432,
        "USER": "myproject",
        "PASSWORD": "password",
        "NAME": "myproject",
    },
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                      "LOCATION": "redis://127.0.0.1:6379/0"}}
```

```bash
docker compose up -d postgres redis
python manage.py migrate
python manage.py createsuperuser  # username: admin
python manage.py runserver 0.0.0.0:8000
```

You'll see:

- `.dev_helpers_token`, `.dev_helpers_port`, `.dev_helpers_pg_*`,
  `.dev_helpers_redis_*` written to project root.
- A browser tab opens on `http://localhost:8000/__autologin__/?token=...`.
- After the first request, the agent help prints to runserver stdout.

## Plain `runserver` (no Docker)

Same setup, just point `DATABASES` at your local Postgres:

```bash
DJANGO_DEV_HELPERS_ENABLED=1 python manage.py runserver
```

Works identically. The lookup chain reads `settings.DATABASES` and
`settings.CACHES` when no env vars or sidecar are present.

## With `django-extensions runserver_plus`

No special handling required. AppConfig.ready runs the same way for any
serving command.

## Activating via env var

If you don't want to commit `DJANGO_DEV_HELPERS = {"enabled": True}` to
`settings.py` (e.g. shared team settings), put `enabled: None` (or omit the
key) and activate per-shell:

```bash
DJANGO_DEV_HELPERS_ENABLED=1 python manage.py runserver
```

A team member who never wants the helpers active can hard-override with:

```python
DJANGO_DEV_HELPERS = {"enabled": False}
```

in `settings.local.py`. Settings False beats env=1.
