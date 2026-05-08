# Configuration reference

All configuration lives in `settings.DJANGO_DEV_HELPERS` (a dict). Every key
has a default; a minimal config is just `{"enabled": True}`.

## Top-level

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | `bool \| None` | `None` | `True`/`False` is a hard override; `None` falls back to `DJANGO_DEV_HELPERS_ENABLED=1` env var. |
| `autologin` | dict | see below | |
| `dotfiles` | dict | see below | |
| `agent_help` | dict | see below | |
| `browser_open` | dict | see below | |
| `gitignore` | dict | see below | |
| `lookup` | dict | see below | DB/Redis discovery chain. |
| `safety` | dict | see below | Production safety check controls. |

Unknown top-level keys raise `ImproperlyConfigured`.

## `autologin`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | `True` | When false, `autologin_urlpatterns()` returns `[]` and the URL doesn't exist. |
| `user_lookup_field` | str | `"username"` | Field used in `User.objects.get(...)`. |
| `user_lookup_value` | str | `"admin"` | Value to match. Can be overridden by `DEV_HELPERS_AUTOLOGIN_USERNAME` env var when not set explicitly. |
| `url_path` | str | `"__autologin__/"` | Path passed to `path()`. |
| `redirect_to` | str | `"/"` | Where the view sends the browser after login. |
| `auth_backend` | str | `"django.contrib.auth.backends.ModelBackend"` | Backend label passed to `login()`. |
| `flash_message` | str | `""` | Optional Django messages flash on login. |
| `extra_cookies` | list[dict] | `[]` | Each dict is `**kwargs` to `HttpResponse.set_cookie`. `name` is accepted as alias for `key`. |
| `allowed_hosts` | list[str] | `[]` | Extra hostnames (glob patterns OK) on top of the default allowlist (`localhost`, `127.0.0.1`, `[::1]`). |

## `dotfiles`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | `True` | |
| `directory` | str \| None | `None` | When `None`, falls back to `DEV_HELPERS_PROJECT_ROOT` env var, then walks up from `BASE_DIR` to find a project marker. |
| `token_filename` | str | `".dev_helpers_token"` | |
| `port_filename` | str | `".dev_helpers_port"` | |
| `pg_host_filename` | str | `".dev_helpers_pg_host"` | |
| `pg_port_filename` | str | `".dev_helpers_pg_port"` | |
| `redis_host_filename` | str | `".dev_helpers_redis_host"` | |
| `redis_port_filename` | str | `".dev_helpers_redis_port"` | |
| `token_chmod` | int | `0o600` | POSIX mode for the token file. Other dotfiles are 0o644. |

## `agent_help`

| Key | Type | Default | Notes |
|---|---|---|---|
| `auto_print` | bool | `True` | Print the prompt to stdout after the first request. |
| `template` | str \| None | `None` | Override the default template. Available placeholders: `host`, `port`, `token_path`, `port_path`, `autologin_path`, `pg_host_path`, `pg_port_path`, `redis_host_path`, `redis_port_path`, `db_user`, `db_password`, `db_name`, `db_user_or_redacted`, `pg_command_with_or_without_password`. |
| `display_host` | str \| None | `None` | When set, used verbatim as the prompt's host string. When `None`, the runserver bind host is used (with `0.0.0.0`/`::` rewritten to `localhost`). |
| `show_db_credentials` | bool | `True` | Set to `False` to keep the DB user/password out of the rendered prompt. |

## `browser_open`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | `True` | |
| `url_path` | str \| None | `None` | When set, browser opens that path; otherwise opens the autologin URL when autologin is enabled, else `/`. |
| `probe_path` | str | `"/admin/login/"` | Self-probe endpoint. |
| `probe_timeout_seconds` | float | `30.0` | Probe gives up after this many seconds. |

The browser is skipped on Linux when neither `DISPLAY` nor `WAYLAND_DISPLAY` is
set.

## `gitignore`

| Key | Type | Default | Notes |
|---|---|---|---|
| `mode` | str | `"warn"` | One of `warn`, `auto-add`, `error`, `off`. Other values raise `ImproperlyConfigured`. |
| `path` | str \| None | `None` | Path to the `.gitignore` to inspect. `None` = `<project_root>/.gitignore`. |

## `lookup`

| Key | Type | Default | Notes |
|---|---|---|---|
| `source` | str | `"auto"` | One of `auto`, `env`, `settings`, `sidecar`. `auto` chains them: callable → env → sidecar → settings, each filling missing keys. |
| `callable` | str \| None | `None` | `"module.path:attr"` — a callable that takes `cfg` and returns a dict with any of `pg_host`, `pg_port`, `db_user`, `db_password`, `db_name`, `redis_host`, `redis_port`. Always runs first when set. |

## `safety`

| Key | Type | Default | Notes |
|---|---|---|---|
| `non_serving_commands` | list[str] | `[]` | Extra management commands that should *not* trigger the production safety check. The built-in list already covers `migrate`, `test`, `shell`, `dbshell`, `collectstatic`, …; add custom commands here when needed. |
