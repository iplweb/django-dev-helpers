# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-08-07

This is a **minor** (not patch) release: it **breaks compatibility** by raising
the Django dependency floor from `>=4.2` to `>=5.2`. See *Removed* below for the
full reasoning and the pin to use if you are stuck on an older Django.

### Added
- **Support for Django 6.1.** The CI matrix now also exercises Django 6.1 on
  Python 3.12 and 3.13 (Django 6.1 requires Python ≥ 3.12, so the 3.11 cell is
  excluded), and the `Framework :: Django :: 6.1` trove classifier was added.

### Removed
- **BREAKING: dropped support for Django 4.2, 5.0 and 5.1.** The minimum
  supported Django is now **5.2**; the dependency floor moved from
  `Django>=4.2` to `Django>=5.2`, the `Framework :: Django :: 4.2/5.0/5.1`
  classifiers were removed, and those rows were dropped from the CI matrix
  (which now covers 5.2, 6.0 and 6.1). Reasons:
  - All three series are past upstream end of life.
  - Django 4.2 was in fact already broken: the ASGI live-reload stream relies
    on `ASGIRequest.listen_for_disconnect()`, which does not exist before
    Django 5.0 — `test_asgi_disconnect_cancels_stream_and_releases_connection`
    hangs there.
  - `pytest-django >= 4.13` itself dropped Django < 5.2.

  If you are still on Django 4.2/5.0/5.1, pin `django-dev-helpers<=0.1.14`.

### Changed
- **CI installs the latest patch of each Django series instead of the initial
  release.** The matrix step now runs
  `uv pip install --system "Django~=${{ matrix.django-version }}.0"` rather than
  `Django==${{ matrix.django-version }}`. `==6.1` resolved to exactly 6.1,
  meaning CI only ever exercised the `.0`-equivalent first release of a series
  (e.g. 6.0 instead of 6.0.8) — not what users actually install.

## [0.1.14] — 2026-07-12

### Fixed
- **Dotfiles (`.dev_helpers_*`) no longer leak on shutdown.** The cleanup
  handler was only registered in the serving `runserver` child, which Django's
  autoreloader **SIGKILLs on shutdown before its `atexit`/SIGTERM cleanup can
  run** — so the token/port dotfiles were left behind on every Ctrl+C. The
  autoreload *parent* process (the file-watcher) exits cleanly on SIGTERM but
  previously skipped all dev-helpers setup. It now registers the dotfile
  *cleanup* (only — it still does not write dotfiles or open the browser), so
  the files are removed when the parent exits. Stale dotfiles pointing at a dead
  port were a frequent source of confusion for tooling/agents that read them.

## [0.1.13] — 2026-07-12

### Fixed
- **Live reload no longer stalls ASGI autoreload.** The `/__dev_reload__/` SSE
  stream was a synchronous generator. Served over an ASGI server
  (daphne/uvicorn — e.g. Django `runserver` with `daphne` in `INSTALLED_APPS`)
  each open connection parked an uninterruptible worker thread in a blocking
  `Event.wait`, so on client disconnect or an autoreload restart the server
  had to wait out `application_close_timeout` and force-kill the instance
  (`took too long to shut down and was killed`) — which stalled the reload.
  `sse_response()` now serves an **async** generator under ASGI (cancelled
  cleanly on disconnect, releasing the connection at once) and keeps the sync
  generator for the classic WSGI `runserver` (which streams a sync iterator
  lazily; an endless async iterator would instead be materialised in full and
  hang). The stream kind is chosen automatically from the request type.

## [0.1.12] — 2026-07-07

### Added
- **Live reload / browser tab reuse.** A tiny SSE client is now injected into
  every `text/html` response; when the server comes back after a restart (or
  Django autoreload) the already-open tab reloads itself instead of a duplicate
  tab being opened. New `LiveReloadMiddleware` (auto-installed, `DEBUG`-gated)
  serves `GET /__dev_reload__/` (SSE, carrying a per-boot `boot_id`) and
  `GET /__dev_reload__/clients` (connected-client count). Before opening its own
  browser tab, dev-helpers samples that count and skips the open when a live tab
  is already connected. New `live_reload` config namespace: `enabled` (True),
  `reuse_tabs` (True), `grace_seconds` (2.0). Caveats: a strict `script-src` CSP
  in DEBUG can block the inline script (disable via `live_reload.enabled=False`);
  closing one of two tabs and restarting reloads the survivor but does not
  reopen the closed one (both tabs live at `/`).

## [0.1.11] — 2026-05-13

### Added
- New `django_dev_helpers.allowed_hosts.inject_allowed_hosts()` reads the
  `DEV_HELPERS_ALLOWED_HOSTS` env var (comma-separated list set by
  `run-site` >= 0.13.0 when binding to a non-loopback address) and unions
  the entries into `settings.ALLOWED_HOSTS` from `AppConfig.ready()`.
  Lets the dev server be reached from phones / other LAN devices without
  per-project `ALLOWED_HOSTS` edits. Idempotent, gated by `is_active()`,
  and a no-op when settings already contain `*` or the var is unset.

## [0.1.10] — 2026-05-12

### Changed
- `manage.py run_site` now detects when it is running under `uv run`
  (via the `UV` env var that uv exports into child processes) and
  pins `run-site` to the current interpreter by injecting
  `--python sys.executable`. This short-circuits `run-site`'s own
  `uv run python` discovery, which would otherwise spawn a second
  `uv run` without the outer `--extra` flags and re-sync the project
  venv — dropping optional dependencies the user had installed for
  this session. Skipped if the user already passes `--python`
  themselves (either `--python /path` or `--python=/path`).

## [0.1.9] — 2026-05-12

### Changed
- `manage.py run_site` no longer requires a `--` separator before flags
  meant for `run-site run`. Anything that isn't a standard Django
  manage.py option (`--verbosity`, `--settings`, `--pythonpath`,
  `--traceback`, `--no-color`, `--force-color`, `--skip-checks`,
  `--version`) is now forwarded verbatim, so
  `manage.py run_site --from-dump=/tmp/x.sql --port 9000` works
  directly. An explicit `--` separator still works and is honored
  verbatim.

## [0.1.8] — 2026-05-12

### Changed
- README now documents the auth-state toggles
  (`?__autologin__=tmp_off|logout|log_in`) and the required middleware
  ordering for manual installs (after `SessionMiddleware`,
  `AuthenticationMiddleware`, and `MessageMiddleware`). The configuration
  example also includes the new `autologin.middleware_autoinstall` and
  `autologin.query_param` keys. No code changes.

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
