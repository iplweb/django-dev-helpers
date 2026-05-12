# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.7] — 2026-05-12

### Added
- `AutologinMiddleware` now also handles three query-string toggles on
  *any* URL, so a developer can flip auth state in the browser without
  navigating to a dedicated URL:
  - `?__autologin__=tmp_off` -- render this one request as anonymous
    (`request.user = AnonymousUser`); session is unchanged so the next
    request without the toggle is logged in again. The toggle param is
    stripped from `request.GET` before the view runs.
  - `?__autologin__=logout` -- `django.contrib.auth.logout(request)`;
    302 to the same path with the toggle stripped. Other query params
    preserved.
  - `?__autologin__=log_in` (or `login`) -- log the configured user in
    (`autologin.user_lookup_field` / `user_lookup_value`); 302 to the
    cleaned URL. No URL token required: the existing host allowlist
    (`refuse_if_unsafe_host`) provides the trust signal, same as for
    the path-based autologin URL.
- New config key `autologin.query_param` (default `"__autologin__"`).
  Rename the toggle, or set to `""` / `None` to disable the toggle
  layer entirely while keeping the path-based autologin URL.
- Unknown toggle values fall through silently (probably a typo); off-host
  toggle requests fall through identically (no 404 / no redirect — would
  leak the toggle's existence).

### Changed
- `docs/autologin.md`, `docs/configuration.md`, and `docs/security.md`
  document the toggles and their threat model.

## [0.1.6] — 2026-05-11

### Added
- New `django_dev_helpers.middleware.AutologinMiddleware` that intercepts
  the autologin URL before URL resolution. With this in place the autologin
  endpoint works without any `urls.py` changes -- projects that have
  `django_dev_helpers` in `INSTALLED_APPS` are fully set up.
- New config flag `autologin.middleware_autoinstall` (default `True`):
  the package now auto-appends `AutologinMiddleware` to
  `settings.MIDDLEWARE` during `AppConfig.ready()`. The entry is appended
  at the end so `SessionMiddleware`, `AuthenticationMiddleware`, and
  `MessageMiddleware` get to set up the request state the view depends on
  (especially `request._messages`, used by `flash_message`). Set the flag
  to `False` to keep the middleware out of `MIDDLEWARE` and continue
  wiring the URL pattern manually with `autologin_urlpatterns()`.
- `AutologinMiddleware.__init__` raises `ImproperlyConfigured` when
  `settings.DEBUG=False`. Defense in depth: if the dev `MIDDLEWARE` list
  ever ends up in a non-dev deployment, the process fails to start rather
  than silently exposing the token-gated login backdoor.

### Changed
- README, `docs/quickstart.md`, `docs/autologin.md`, `docs/configuration.md`,
  and `docs/security.md` updated to reflect the zero-config setup and the
  new middleware path.
- The "autologin URL returned 404" banner (introduced in 0.1.5) now lists
  all three failure modes (app not in `INSTALLED_APPS`, auto-install
  disabled, autologin disabled) so the user can pick the relevant fix.
- pytest configuration: `django_debug_mode = "keep"` so tests run with
  `DEBUG=True` (matching real-world usage; required for the middleware to
  load).

## [0.1.5] — 2026-05-11

### Added
- Browser-opening flow now HEAD-probes the autologin URL before opening
  it. If the URL responds with 404 (e.g. because the user installed the
  package but forgot to wire `*autologin_urlpatterns()` into their
  `urls.py`), django-dev-helpers prints a banner explaining how to enable
  autologin (or disable it in settings) and opens `http://<host>:<port>/`
  instead — so the user lands on the home page rather than a Django 404
  debug page. HEAD is used to avoid triggering a real autologin side
  effect during the probe. Connection errors during the probe fall back
  to the previous behavior (open the autologin URL anyway).

## [0.1.4] — 2026-05-11

### Fixed
- `run_site` management command now auto-injects `--manage-py <abs path>`
  into the forwarded `run-site run` arguments when invoked through a
  specific `manage.py` (e.g. `python example_grappelli/manage.py run_site`).
  Previously, projects shipping multiple example/manage.py files would
  error out with `Multiple Django manage.py files found … Pass --manage-py
  or set 'manage_py' in runsite.toml to disambiguate.` even though the
  user had already picked one by invoking it. The injection is skipped
  when `--manage-py` (or `--manage-py=…`) is already in the forwarded
  args, or when `sys.argv[0]` does not look like a `manage.py`
  (e.g. `django-admin`).

## [0.1.3] — 2026-05-11

This release rolls up the post-0.1.2 work that had been accumulating
under *Unreleased* together with a batch of fresh bug fixes around the
agent-help banner and a new gitignore-fix management command.

### Added
- `dev_helpers_fix_gitignore` management command — idempotent, append-only
  one-shot way to add the dev-helpers dotfile names to `.gitignore`. Use
  it when you see the "missing entries from .gitignore" warning and you
  don't want to flip `gitignore.mode = "auto-add"` globally. `--dry-run`
  previews changes without writing. Documented in
  `docs/configuration.md#gitignore`.
- Banner and AGENTS.md / CLAUDE.md static block are now **engine-aware**:
  SQLite-backed projects see a `SQLite` section with the database file
  path and the `sqlite3` invocation; PostgreSQL-only / Redis-less projects
  see only the sections that apply. The previous one-size-fits-all
  template advertised PostgreSQL + Redis even when those services were
  not part of the stack.
- `lookup.source = "sidecar"` and inclusion of the run-site
  `.run-site-config` TOML file in the `auto` lookup chain. Order is now:
  callable → env → sidecar → settings.
- `lookup.callable = "module:attr"` — full primary endpoint resolver,
  pluggable per project.
- `DEV_HELPERS_AUTOLOGIN_USERNAME` env var picked up as the autologin
  user when `autologin.user_lookup_value` is not set explicitly.
- Config validation in `conf.py` — unknown keys, invalid `gitignore.mode`,
  invalid `lookup.source`, malformed `extra_cookies`, etc. raise
  `ImproperlyConfigured` at app load.
- `dev_helpers_doctor` now reports `.run-site-config` parse status and
  warns when legacy `.run_site_*` files are present in the project root.
- `docs/` directory with quickstart, configuration, autologin, dotfiles,
  agent-help, standalone-usage, with-django-run-site, security guides.
- Tests for the sidecar reader, config validation, view HTTP-method
  restriction, AppConfig.ready orchestration, and a real-subprocess test
  for token autoreload behavior.

### Changed
- Autologin view now restricted to `GET`
  (`@require_http_methods(["GET"])`).
- Agent help prompt `shlex.quote`-s the DB user/password/name so passwords
  containing quotes/spaces survive the shell snippet.
- SIGTERM cleanup chains to the previously-installed handler instead of
  replacing it; cleanup is idempotent across atexit + SIGTERM paths.
- Browser auto-open and agent-help auto-print fire at most once per dev
  session — re-runs of `AppConfig.ready()` (via Django's autoreloader)
  are gated by `DEV_HELPERS_BROWSER_OPENED` / `DEV_HELPERS_HELP_PRINTED`
  sentinel env vars.
- Dotfile atomic writes now set explicit modes (token = `0o600`, others =
  `0o644`) — the temp-file mode no longer leaks 0o600 to non-secret files.
- Browser self-probe catches a narrow set of expected exceptions and no
  longer logs every failed attempt with a traceback.
- Browser open is skipped on Linux without `DISPLAY`/`WAYLAND_DISPLAY`.
- `gitignore` mode warning now goes through `logger.warning` instead of
  `print(stderr)`.

### Fixed
- `prompt.render_template` no longer raises
  `TypeError: expected string or bytes-like object, got 'PosixPath'`
  when `DATABASES['default']['NAME']` is a `pathlib.Path` (the standard
  SQLite shape, `BASE_DIR / "db.sqlite3"`). DB string fields read from
  settings are now coerced to `str` before being passed to
  `shlex.quote` / `.format()`.
- `prompt.render_template` no longer produces
  `Server is up at: http://localhost:None` when `discover_port` returns
  `None` (e.g. `manage.py run_site` rendering the suggestion block
  before the dev server has started). The line now falls back to
  `http://{host}:$PORT (read $PORT from the dotfile below)`, which is
  copy-paste-correct under shell expansion.
- `manage.py run_site` now suggests `render_static_agent_help_block`
  (the dotfile-referencing version with paired markers) instead of the
  runtime banner. Pasting the static block into AGENTS.md / CLAUDE.md
  doesn't go stale across restarts that pick a different free port.
- `pyproject.toml` `pythonpath` now includes the repo root so `pytest`
  works without a manual `PYTHONPATH=.`.
- `pyproject.toml` `[dev]` extras now include `ruff` and `mypy` so CI
  steps using them pass after `uv pip install -e ".[dev]"`.
- `pyproject.toml` adds `[project.urls]` for OSS hygiene.
- `__init__.py` exposes `__version__`.

## [0.1.0] - 2026-05-07

### Added
- Autologin endpoint with token-based authentication
- Dotfile management (token, port, PG, Redis)
- Agent help / prompt template
- Gitignore self-check
- Browser auto-open with self-probe
- Production safety kill switch
- `dev_helpers_doctor` management command
- `dev_helpers_print_help` management command
- `dev_helpers_check_gitignore` management command
