# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `lookup.source = "sidecar"` and inclusion of the run-site `.run-site-config`
  TOML file in the `auto` lookup chain. Order is now: callable → env →
  sidecar → settings.
- `lookup.callable = "module:attr"` — full primary endpoint resolver,
  pluggable per project.
- `DEV_HELPERS_AUTOLOGIN_USERNAME` env var picked up as the autologin user
  when `autologin.user_lookup_value` is not set explicitly.
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
- Autologin view now restricted to `GET` (`@require_http_methods(["GET"])`).
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
