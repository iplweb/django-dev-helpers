from __future__ import annotations

import os
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.fixture
def project_dir(tmp_path):
    os.environ["DEV_HELPERS_PORT"] = "8000"
    yield tmp_path
    os.environ.pop("DEV_HELPERS_PORT", None)


def _call(*args, settings_override=None, **kwargs):
    err = StringIO()
    out = StringIO()
    overrides = settings_override or {"enabled": True}
    with override_settings(DJANGO_DEV_HELPERS=overrides):
        call_command("run_site", *args, stderr=err, stdout=out, **kwargs)
    return out.getvalue(), err.getvalue()


def test_errors_when_run_site_binary_missing(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("shutil.which", return_value=None), pytest.raises(CommandError, match="run-site is not installed"):
        _call(settings_override=overrides)


def test_passes_args_through_to_run_site(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site") as spawn:
        _call("--", "--port", "9000", "--no-browser", settings_override=overrides)
    spawn.assert_called_once_with(["run", "--port", "9000", "--no-browser"])


def test_no_args_invokes_run_site_run(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site") as spawn:
        _call(settings_override=overrides)
    spawn.assert_called_once_with(["run"])


def test_claude_md_suggestion_emitted_when_marker_missing(project_dir):
    (project_dir / "CLAUDE.md").write_text("# Project notes\n\nSome content.\n", encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site"):
        _, err = _call(settings_override=overrides)
    assert "[dev-helpers] Tip:" in err
    assert "CLAUDE.md" in err
    assert "<!-- django-dev-helpers:agent-help -->" in err


def test_claude_md_suggestion_silent_when_marker_present(project_dir):
    marker = "<!-- django-dev-helpers:agent-help -->"
    (project_dir / "CLAUDE.md").write_text(f"# Project\n\n{marker}\n\nblah\n", encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site"):
        _, err = _call(settings_override=overrides)
    assert "[dev-helpers] Tip:" not in err


def test_claude_md_suggestion_silent_when_mode_off(project_dir):
    (project_dir / "CLAUDE.md").write_text("# nothing here\n", encoding="utf-8")
    overrides = {
        "enabled": True,
        "dotfiles": {"directory": str(project_dir)},
        "claude_md": {"mode": "off"},
    }
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site"):
        _, err = _call(settings_override=overrides)
    assert "[dev-helpers] Tip:" not in err


def test_claude_md_suggestion_when_no_files_exist(project_dir):
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site"):
        _, err = _call(settings_override=overrides)
    assert "[dev-helpers] Tip:" in err
    assert "CLAUDE.md or AGENTS.md" in err


def test_claude_md_marker_in_agents_md_silences_for_both(project_dir):
    marker = "<!-- django-dev-helpers:agent-help -->"
    (project_dir / "CLAUDE.md").write_text("# no marker here\n", encoding="utf-8")
    (project_dir / "AGENTS.md").write_text(f"# agents\n{marker}\n", encoding="utf-8")
    overrides = {"enabled": True, "dotfiles": {"directory": str(project_dir)}}
    with patch("django_dev_helpers.management.commands.run_site.spawn_run_site"):
        _, err = _call(settings_override=overrides)
    assert "[dev-helpers] Tip:" not in err


def test_claude_md_invalid_mode_rejected_at_config_load():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"claude_md": {"mode": "bogus"}}),
        pytest.raises(ImproperlyConfigured, match=r"claude_md.*mode"),
    ):
        DevHelpersConfig()


def test_claude_md_files_must_be_list_of_strings():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"claude_md": {"files": "CLAUDE.md"}}),
        pytest.raises(ImproperlyConfigured, match=r"files.*list of strings"),
    ):
        DevHelpersConfig()


def test_claude_md_marker_must_be_non_empty():
    from django_dev_helpers.conf import DevHelpersConfig

    with (
        override_settings(DJANGO_DEV_HELPERS={"claude_md": {"marker": ""}}),
        pytest.raises(ImproperlyConfigured, match=r"marker.*non-empty"),
    ):
        DevHelpersConfig()
