# Repository Guidelines

## Project Structure & Module Organization

This is a Python package using a `src/` layout. Runtime code lives in `src/django_dev_helpers/`, including Django views, URL helpers, safety checks, configuration, dotfile support, browser opening, and management commands under `management/commands/`. Tests live in `tests/` and use the local Django settings module in `tests/settings.py`. Documentation is in `docs/`, with the frozen design spec in `docs/design/`. CI is defined in `.github/workflows/ci.yml`; packaging metadata and tool configuration are in `pyproject.toml`.

## Build, Test, and Development Commands

- `uv sync --extra dev`: install the package and development tools into the local environment.
- `uv run pytest`: run the full pytest suite with `pytest-django`.
- `uv run pytest tests/test_autologin_view.py`: run a focused test file.
- `uv run ruff check .`: lint imports, pyupgrade rules, bugbear checks, and project style rules.
- `uv run ruff format .`: format Python files.
- `uv run mypy src/django_dev_helpers`: run type checks with Django stubs.
- `uv build`: build the distributable package with Hatchling.

## Coding Style & Naming Conventions

Target Python 3.11 and keep code compatible with Django 4.2 through 5.2. Use 4-space indentation, typed public helpers where practical, and clear snake_case names for modules, functions, fixtures, and settings keys. Management commands should follow Django naming conventions, such as `dev_helpers_doctor.py`. Ruff is the source of truth for formatting and linting; line length is 120 characters.

## Testing Guidelines

Tests use `pytest`, `pytest-django`, and Django’s test database. Name tests `test_*.py` and test functions `test_<behavior>`. Prefer focused tests near the behavior being changed, and update fixtures in `tests/conftest.py` only when the setup is broadly useful. Run `uv run pytest` before submitting changes; run `uv run mypy src/django_dev_helpers` when public APIs, settings, or Django integration points change.

## Commit & Pull Request Guidelines

Recent commits use short, direct, capitalized subjects without prefixes, for example `Point CI badge and project URLs at iplweb org`. Keep the first line concise and describe the observable change. Pull requests should include a short summary, test results, linked issues when relevant, and docs updates for user-facing behavior. Include screenshots only for rendered documentation or browser-visible behavior.

## Security & Configuration Tips

This package provides development-only conveniences, including an autologin endpoint and generated dotfiles. Do not weaken the `DEBUG=False` safeguards, token checks, localhost restrictions, or failure behavior without updating `docs/security.md` and adding regression tests. Never commit generated `.dev_helpers_*` files or local secrets.
