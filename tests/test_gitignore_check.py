
import pytest
from django.test import override_settings


@pytest.fixture
def git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def cfg_with_gitignore(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(git_dir)},
            "gitignore": {"mode": "warn", "path": str(git_dir / ".gitignore")},
        }
    ):
        cfg = DevHelpersConfig()
        yield cfg


def test_all_entries_present(cfg_with_gitignore, git_dir):
    from django_dev_helpers.gitignore import get_missing_entries

    content = "\n".join([
        ".dev_helpers_token",
        ".dev_helpers_port",
        ".dev_helpers_pg_host",
        ".dev_helpers_pg_port",
        ".dev_helpers_redis_host",
        ".dev_helpers_redis_port",
    ])
    missing = get_missing_entries(content)
    assert missing == []


def test_missing_entries(cfg_with_gitignore, git_dir):
    from django_dev_helpers.gitignore import get_missing_entries

    content = ".dev_helpers_token\n"
    missing = get_missing_entries(content)
    assert ".dev_helpers_port" in missing


def test_mode_warn(cfg_with_gitignore, git_dir, caplog):
    import logging

    from django_dev_helpers.gitignore import check_gitignore

    gitignore_file = git_dir / ".gitignore"
    gitignore_file.write_text(".dev_helpers_token\n")

    from django_dev_helpers.conf import DevHelpersConfig

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(git_dir)},
            "gitignore": {"mode": "warn", "path": str(gitignore_file)},
        }
    ):
        from django_dev_helpers.conf import reset_config
        reset_config()
        cfg = DevHelpersConfig()
        with caplog.at_level(logging.WARNING, logger="django_dev_helpers.gitignore"):
            check_gitignore(cfg)
        assert any("missing" in rec.message.lower() for rec in caplog.records)


def test_mode_auto_add(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import check_gitignore

    gitignore_file = git_dir / ".gitignore"
    gitignore_file.write_text("*.pyc\n")

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(git_dir)},
            "gitignore": {"mode": "auto-add", "path": str(gitignore_file)},
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        check_gitignore(cfg)
        content = gitignore_file.read_text()
        assert ".dev_helpers_token" in content
        assert ".dev_helpers_port" in content


def test_mode_error(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import check_gitignore

    gitignore_file = git_dir / ".gitignore"
    gitignore_file.write_text("*.pyc\n")

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(git_dir)},
            "gitignore": {"mode": "error", "path": str(gitignore_file)},
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        with pytest.raises(SystemExit):
            check_gitignore(cfg)


def test_no_git_dir(tmp_path):
    from django_dev_helpers.conf import DevHelpersConfig
    from django_dev_helpers.gitignore import check_gitignore

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {"directory": str(tmp_path)},
        }
    ):
        cfg = DevHelpersConfig()
        result = check_gitignore(cfg)
        assert result is None


def test_required_entries_uses_custom_filenames(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import required_entries

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {
                "directory": str(git_dir),
                "token_filename": ".my_token",
                "port_filename": ".my_port",
                "pg_host_filename": ".my_pg_host",
                "pg_port_filename": ".my_pg_port",
                "redis_host_filename": ".my_redis_host",
                "redis_port_filename": ".my_redis_port",
            },
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        assert required_entries(cfg) == [
            ".my_token",
            ".my_port",
            ".my_pg_host",
            ".my_pg_port",
            ".my_redis_host",
            ".my_redis_port",
        ]


def test_get_missing_entries_with_cfg_uses_custom_filenames(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import get_missing_entries

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {
                "directory": str(git_dir),
                "token_filename": ".my_token",
            },
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        # Default token name is present, but the configured custom name is not.
        content = ".dev_helpers_token\n"
        missing = get_missing_entries(content, cfg)
        assert ".my_token" in missing
        assert ".dev_helpers_token" not in missing


def test_warn_uses_custom_token_filename(git_dir, caplog):
    import logging

    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import check_gitignore

    gitignore_file = git_dir / ".gitignore"
    gitignore_file.write_text("")

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {
                "directory": str(git_dir),
                "token_filename": ".secret_token_xyz",
            },
            "gitignore": {"mode": "warn", "path": str(gitignore_file)},
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        with caplog.at_level(logging.WARNING, logger="django_dev_helpers.gitignore"):
            check_gitignore(cfg)
        combined = "\n".join(rec.message for rec in caplog.records)
        assert ".secret_token_xyz" in combined
        # Default name must not be reported when a custom one is configured.
        assert ".dev_helpers_token" not in combined


def test_auto_add_writes_custom_filenames(git_dir):
    from django_dev_helpers.conf import DevHelpersConfig, reset_config
    from django_dev_helpers.gitignore import check_gitignore

    gitignore_file = git_dir / ".gitignore"
    gitignore_file.write_text("*.pyc\n")

    with override_settings(
        DJANGO_DEV_HELPERS={
            "enabled": True,
            "dotfiles": {
                "directory": str(git_dir),
                "token_filename": ".secret_token_xyz",
                "port_filename": ".my_port_file",
            },
            "gitignore": {"mode": "auto-add", "path": str(gitignore_file)},
        }
    ):
        reset_config()
        cfg = DevHelpersConfig()
        check_gitignore(cfg)
        content = gitignore_file.read_text()
        assert ".secret_token_xyz" in content
        assert ".my_port_file" in content
        assert ".dev_helpers_token" not in content
        assert ".dev_helpers_port" not in content
