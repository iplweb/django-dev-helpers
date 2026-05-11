from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.fixture
def project_dir(tmp_path):
    """An isolated project directory; .git is not required since the fix
    command should run on explicit user invocation regardless."""

    return tmp_path


def _run(*args, settings_override):
    stdout = StringIO()
    stderr = StringIO()
    with override_settings(DJANGO_DEV_HELPERS=settings_override):
        call_command("dev_helpers_fix_gitignore", *args, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


def test_creates_gitignore_when_missing(project_dir):
    """A project with no .gitignore at all gets one with all dev-helpers
    dotfile entries — the command is the first-time setup path, not just
    a patch-up step."""

    gi = project_dir / ".gitignore"
    assert not gi.exists()
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    out, _ = _run(settings_override=overrides)
    assert gi.is_file()
    body = gi.read_text(encoding="utf-8")
    for entry in (
        ".dev_helpers_token",
        ".dev_helpers_port",
        ".dev_helpers_pg_host",
        ".dev_helpers_pg_port",
        ".dev_helpers_redis_host",
        ".dev_helpers_redis_port",
    ):
        assert entry in body
    assert "Added 6 entries" in out


def test_appends_only_missing_entries(project_dir):
    """Idempotency contract: pre-existing entries are kept verbatim and
    not duplicated; only the genuinely-missing names are appended."""

    gi = project_dir / ".gitignore"
    gi.write_text("*.pyc\n.dev_helpers_token\n", encoding="utf-8")
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    out, _ = _run(settings_override=overrides)

    body = gi.read_text(encoding="utf-8")
    # Original lines preserved as-is, no duplicates.
    assert body.count("*.pyc") == 1
    assert body.count(".dev_helpers_token") == 1
    # All other expected entries now present.
    assert ".dev_helpers_port" in body
    assert ".dev_helpers_pg_host" in body
    assert ".dev_helpers_redis_port" in body
    # The summary mentions the count of *appended* entries (5, not 6).
    assert "Added 5 entries" in out


def test_idempotent_when_all_present(project_dir):
    """Running the command twice in a row is a no-op the second time."""

    gi = project_dir / ".gitignore"
    gi.write_text(
        "\n".join(
            [
                ".dev_helpers_token",
                ".dev_helpers_port",
                ".dev_helpers_pg_host",
                ".dev_helpers_pg_port",
                ".dev_helpers_redis_host",
                ".dev_helpers_redis_port",
                "",
            ]
        ),
        encoding="utf-8",
    )
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    before = gi.read_text(encoding="utf-8")
    out, _ = _run(settings_override=overrides)
    after = gi.read_text(encoding="utf-8")
    assert before == after
    assert "already present" in out


def test_dry_run_does_not_write(project_dir):
    gi = project_dir / ".gitignore"
    gi.write_text("*.pyc\n", encoding="utf-8")
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    out, _ = _run("--dry-run", settings_override=overrides)
    assert gi.read_text(encoding="utf-8") == "*.pyc\n"
    assert "Would add" in out
    assert ".dev_helpers_token" in out


def test_respects_custom_dotfile_filenames(project_dir):
    """Projects that override dotfile names (via ``dotfiles.*_filename``)
    must get those custom names written, not the defaults."""

    gi = project_dir / ".gitignore"
    overrides = {
        "enabled": True,
        "dotfiles": {
            "directory": str(project_dir),
            "token_filename": ".my_token",
            "port_filename": ".my_port",
        },
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    _run(settings_override=overrides)
    body = gi.read_text(encoding="utf-8")
    assert ".my_token" in body
    assert ".my_port" in body
    # Defaults must not leak in when the user re-named the dotfiles.
    assert ".dev_helpers_token" not in body
    assert ".dev_helpers_port" not in body


def test_appends_without_clobbering_trailing_newline(project_dir):
    """The original content was missing a trailing newline; we add one
    before our block so existing and new entries don't end up on the
    same line."""

    gi = project_dir / ".gitignore"
    gi.write_text("*.pyc", encoding="utf-8")  # no trailing newline
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "gitignore": {"mode": "off", "path": str(gi)},
    }
    _run(settings_override=overrides)
    body = gi.read_text(encoding="utf-8")
    # The line we added must start on its own line.
    assert "*.pyc\n" in body
    assert "*.pyc.dev_helpers_token" not in body
