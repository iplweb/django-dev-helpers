# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
