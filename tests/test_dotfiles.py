import os
import stat
from unittest.mock import patch

import pytest
from django.test import override_settings


@pytest.fixture
def dotfile_dir(tmp_path):
    return tmp_path


@pytest.fixture
def cfg_with_dir(dotfile_dir):
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(dotfile_dir)},
        }
    ):
        cfg = DevHelpersConfig()
        yield cfg


def test_write_token_file(cfg_with_dir, dotfile_dir):
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = "my-secret-token"
    from django_dev_helpers.dotfiles import write_all_dotfiles

    write_all_dotfiles(cfg_with_dir)
    token_file = dotfile_dir / ".dev_helpers_token"
    assert token_file.exists()
    assert token_file.read_text() == "my-secret-token"
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_write_port_file(cfg_with_dir, dotfile_dir):
    os.environ["DEV_HELPERS_PORT"] = "49152"
    from django_dev_helpers.dotfiles import write_all_dotfiles

    write_all_dotfiles(cfg_with_dir)
    port_file = dotfile_dir / ".dev_helpers_port"
    assert port_file.exists()
    assert port_file.read_text() == "49152"
    os.environ.pop("DEV_HELPERS_PORT", None)


def test_cleanup_removes_files(cfg_with_dir, dotfile_dir):
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = "token"
    from django_dev_helpers.dotfiles import remove_all_dotfiles, write_all_dotfiles

    write_all_dotfiles(cfg_with_dir)
    assert (dotfile_dir / ".dev_helpers_token").exists()
    remove_all_dotfiles(cfg_with_dir)
    assert not (dotfile_dir / ".dev_helpers_token").exists()
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_chmod_token(cfg_with_dir, dotfile_dir):
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = "token"
    from django_dev_helpers.dotfiles import write_all_dotfiles

    write_all_dotfiles(cfg_with_dir)
    token_file = dotfile_dir / ".dev_helpers_token"
    if os.name != "nt":
        mode = stat.S_IMODE(os.stat(token_file).st_mode)
        assert mode == 0o600
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_resolve_project_root_from_env(tmp_path):
    from django_dev_helpers.conf import DevHelpersConfig

    os.environ["DEV_HELPERS_PROJECT_ROOT"] = str(tmp_path)
    with override_settings(DJANGO_DEV_HELPERS={"enabled": True}):
        from django_dev_helpers.project_root import resolve_project_root

        cfg = DevHelpersConfig()
        result = resolve_project_root(cfg)
        assert result == tmp_path.resolve()
    os.environ.pop("DEV_HELPERS_PROJECT_ROOT", None)


def test_write_skip_none_values(cfg_with_dir, dotfile_dir):
    from django_dev_helpers.dotfiles import write_all_dotfiles

    os.environ.pop("DEV_HELPERS_PORT", None)
    with patch("django_dev_helpers.dotfiles.discover_port", return_value=None):
        write_all_dotfiles(cfg_with_dir)
    assert not (dotfile_dir / ".dev_helpers_port").exists()
