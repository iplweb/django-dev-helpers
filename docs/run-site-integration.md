# `manage.py run_site`

`manage.py run_site` wraps the [`run-site`](https://github.com/iplweb/run-site) CLI orchestrator so it can be invoked from inside a Django project the same way you invoke any other management command. It executes `run-site run` with the same conveniences `run-site` provides on its own (Postgres + Redis containers, dump restore, `runserver`, browser open), and adds a one-shot reminder to keep your `CLAUDE.md` / `AGENTS.md` agent prompt up to date.

## Requirements

- The `run-site` CLI must be on `PATH`.
  - Recommended: `uv tool install run-site`
  - Or in the project venv: `uv add --dev run-site`
- `django_dev_helpers` must be in `INSTALLED_APPS`.

## Usage

```bash
python manage.py run_site
```

Forward extra flags to `run-site run` directly:

```bash
python manage.py run_site --port 9000 --no-browser --no-migrate
python manage.py run_site --from-dump=/tmp/site.sql
```

Anything that isn't a standard Django manage.py option (`--verbosity`, `--settings`, `--pythonpath`, `--traceback`, `--no-color`, `--force-color`, `--skip-checks`) is forwarded verbatim to `run-site run`. You can still pass an explicit `--` separator if you want to be precise about it:

```bash
python manage.py run_site --verbosity 2 -- --port 9000
```

## Agent help block hint

On every invocation `run_site` checks whether the project has an agent prompt block in `CLAUDE.md` or `AGENTS.md`. If neither file contains the marker line `<!-- django-dev-helpers:agent-help -->`, `run_site` prints a copy-pasteable block with:

- the marker line (so the next run is silent once you paste it in)
- a fenced code block containing the same agent prompt that `manage.py dev_helpers_print_help` produces

Paste it into one of the candidate files and the hint silences itself.

### Configuration

```python
DJANGO_DEV_HELPERS = {
    "claude_md": {
        "mode": "warn",  # "warn" (default) or "off"
        "files": ["CLAUDE.md", "AGENTS.md"],
        "marker": "<!-- django-dev-helpers:agent-help -->",
    },
}
```

- `mode = "off"` silences the hint globally for the project.
- `files` controls which filenames are checked. List order is also the suggestion order.
- `marker` is the literal string searched for in those files. Change it if the default collides with something else in your repo.

## What `run_site` does *not* do

- It does not duplicate `run-site run` flags. They are passed through verbatim.
- It does not write anything to `CLAUDE.md` / `AGENTS.md` automatically — only suggests.
- It does not start a Django server itself. The actual `runserver` is launched by `run-site`, in a fresh subprocess that picks up the `DEV_HELPERS_*` env-var contract.
