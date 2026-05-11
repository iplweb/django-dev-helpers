from __future__ import annotations

import os
import sys
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

MARKER = "<!-- django-dev-helpers:agent-help -->"
END_MARKER = "<!-- django-dev-helpers:agent-help-end -->"


@pytest.fixture
def project_dir(tmp_path):
    yield tmp_path


def _call(*args, settings_override=None, stdin_text=None):
    out = StringIO()
    err = StringIO()
    overrides = settings_override or {"enabled": True}
    saved_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = StringIO(stdin_text)
    try:
        with override_settings(DJANGO_DEV_HELPERS=overrides):
            call_command("dev_helpers_enable_agent_helpers", *args, stdout=out, stderr=err)
    finally:
        sys.stdin = saved_stdin
    return out.getvalue(), err.getvalue()


def test_creates_agents_md_when_neither_exists_non_interactive(project_dir):
    # Force a Postgres + Redis-backed project so the generated block
    # exercises every dotfile filename. Sqlite-only / no-redis projects
    # legitimately omit those sections (covered by separate tests).
    overrides = {
        "enabled": True,
        "lookup": {"source": "settings"},
        "dotfiles": {"directory": str(project_dir)},
    }
    databases = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "127.0.0.1",
            "PORT": "5432",
            "NAME": "demo",
            "USER": "demo",
            "PASSWORD": "demo-pwd",
        }
    }
    caches = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/0",
        }
    }
    with override_settings(DATABASES=databases, CACHES=caches):
        out, _ = _call("--non-interactive", settings_override=overrides)
    assert (project_dir / "AGENTS.md").is_file()
    assert not (project_dir / "CLAUDE.md").exists()
    assert "Created AGENTS.md" in out
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert MARKER in body
    assert END_MARKER in body
    assert ".dev_helpers_token" in body
    assert ".dev_helpers_port" in body
    assert ".dev_helpers_pg_host" in body
    assert ".dev_helpers_redis_host" in body


def test_appends_to_existing_agents_md(project_dir):
    (project_dir / "AGENTS.md").write_text("# Project notes\n\nExisting content.\n", encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    out, _ = _call("--non-interactive", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Project notes" in body
    assert "Existing content." in body
    assert MARKER in body
    assert END_MARKER in body
    assert "Appended agent-help block to AGENTS.md" in out


def test_idempotent_when_marker_present(project_dir):
    pre_content = f"# Notes\n\n{MARKER}\nstale block\n{END_MARKER}\n"
    (project_dir / "AGENTS.md").write_text(pre_content, encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    out, _ = _call("--non-interactive", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert body == pre_content
    assert "marker already present" in out


def test_force_replaces_block_in_place(project_dir):
    pre_content = f"# Notes\n\n{MARKER}\nstale\n{END_MARKER}\n\nMore notes after.\n"
    (project_dir / "AGENTS.md").write_text(pre_content, encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    out, _ = _call("--non-interactive", "--force", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "stale" not in body
    assert "# Notes" in body
    assert "More notes after." in body
    assert ".dev_helpers_token" in body
    assert "Replaced existing agent-help block in AGENTS.md" in out


def test_force_handles_legacy_block_without_end_marker(project_dir):
    pre_content = f"# Notes\n\n{MARKER}\nlegacy block with no end marker\n"
    (project_dir / "AGENTS.md").write_text(pre_content, encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _call("--non-interactive", "--force", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "legacy block with no end marker" not in body
    assert MARKER in body
    assert END_MARKER in body


def test_uses_existing_files_when_no_target_specified(project_dir):
    (project_dir / "CLAUDE.md").write_text("# C\n", encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _call(settings_override=overrides)
    body = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert MARKER in body
    assert not (project_dir / "AGENTS.md").exists()


def test_target_flag_explicit_creates_only_specified_file(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _call("--target", "CLAUDE.md", "--non-interactive", settings_override=overrides)
    assert (project_dir / "CLAUDE.md").is_file()
    assert not (project_dir / "AGENTS.md").exists()


def test_target_flag_can_be_repeated_for_both(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _call(
        "--target",
        "AGENTS.md",
        "--target",
        "CLAUDE.md",
        "--non-interactive",
        settings_override=overrides,
    )
    assert (project_dir / "AGENTS.md").is_file()
    assert (project_dir / "CLAUDE.md").is_file()


def test_target_unknown_filename_rejected(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with pytest.raises(CommandError, match=r"--target 'README\.md' is not in"):
        _call("--target", "README.md", "--non-interactive", settings_override=overrides)


def test_skips_symlink_target(project_dir):
    if os.name == "nt":
        pytest.skip("symlink semantics differ on Windows")
    real = project_dir / "AGENTS.md"
    real.write_text("# real\n", encoding="utf-8")
    link = project_dir / "CLAUDE.md"
    link.symlink_to(real.name)

    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _, err = _call(
        "--target",
        "AGENTS.md",
        "--target",
        "CLAUDE.md",
        "--non-interactive",
        settings_override=overrides,
    )
    assert "Skipping CLAUDE.md" in err
    assert link.is_symlink()
    body = real.read_text(encoding="utf-8")
    assert body.count(MARKER) == 1


def test_interactive_prompt_choosing_both(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    _call(settings_override=overrides, stdin_text="b\n")
    assert (project_dir / "AGENTS.md").is_file()
    assert (project_dir / "CLAUDE.md").is_file()


def test_interactive_prompt_skip(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    out, _ = _call(settings_override=overrides, stdin_text="s\n")
    assert not (project_dir / "AGENTS.md").exists()
    assert not (project_dir / "CLAUDE.md").exists()
    assert "Nothing to do." in out


def test_interactive_prompt_invalid_then_valid(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    out, _ = _call(settings_override=overrides, stdin_text="zzz\na\n")
    assert (project_dir / "AGENTS.md").is_file()
    assert "Please answer" in out


def test_interactive_eof_raises_command_error(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with pytest.raises(CommandError, match="stdin is not a TTY"):
        _call(settings_override=overrides, stdin_text="")


def test_block_uses_configured_dotfile_filenames(project_dir):
    overrides = {
        "enabled": True,
        "dotfiles": {
            "directory": str(project_dir),
            "token_filename": ".my_token",
            "port_filename": ".my_port",
        },
    }
    _call("--non-interactive", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert ".my_token" in body
    assert ".my_port" in body
    assert ".dev_helpers_token" not in body


def test_block_uses_configured_marker(project_dir):
    custom_start = "<!-- my-marker -->"
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "claude_md": {"marker": custom_start},
    }
    _call("--non-interactive", settings_override=overrides)
    body = (project_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert custom_start in body
    assert "<!-- my-marker-end -->" in body


def test_mode_off_still_runs_when_invoked_explicitly(project_dir):
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "claude_md": {"mode": "off"},
    }
    _, err = _call("--non-interactive", settings_override=overrides)
    assert (project_dir / "AGENTS.md").is_file()
    assert "claude_md.mode is 'off'" in err
