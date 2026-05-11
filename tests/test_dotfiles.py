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


def test_discover_bind_host_no_arg(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])
    assert discover_bind_host() == "localhost"


def test_discover_bind_host_port_only(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "9000"])
    assert discover_bind_host() == "localhost"


def test_discover_bind_host_localhost_with_port(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "localhost:9000"])
    assert discover_bind_host() == "localhost"


def test_discover_bind_host_all_zeros(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "0.0.0.0:9000"])
    assert discover_bind_host() == "localhost"


def test_discover_bind_host_loopback_ip(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "127.0.0.1:9000"])
    assert discover_bind_host() == "127.0.0.1"


def test_discover_bind_host_lan_ip(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "192.168.1.10:9000"])
    assert discover_bind_host() == "192.168.1.10"


def test_discover_bind_host_ipv6_unspecified(monkeypatch):
    import sys

    from django_dev_helpers.dotfiles import discover_bind_host

    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "::"])
    assert discover_bind_host() == "localhost"


def _write_min_sidecar(directory, *, port=49152, host="127.0.0.1"):
    """Write a minimal .run-site-config exposing only the [web] section."""
    (directory / ".run-site-config").write_text(
        f'project_slug = "x"\n[web]\nhost = "{host}"\nport = {port}\n',
        encoding="utf-8",
    )


def test_discover_port_falls_back_to_sidecar(monkeypatch, tmp_path):
    """run-site orchestrator path: no 'runserver' in argv, port comes from sidecar."""
    import sys

    monkeypatch.delenv("DEV_HELPERS_PORT", raising=False)
    monkeypatch.setattr(sys, "argv", ["run-site", "run"])
    _write_min_sidecar(tmp_path, port=65359)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "dotfiles": {"directory": str(tmp_path)}}):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.dotfiles import discover_port

        reset_config()
        cfg = DevHelpersConfig()
        assert discover_port(cfg) == "65359"


def test_discover_bind_host_falls_back_to_sidecar(monkeypatch, tmp_path):
    import sys

    monkeypatch.setattr(sys, "argv", ["run-site", "run"])
    _write_min_sidecar(tmp_path, host="example.local")

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "dotfiles": {"directory": str(tmp_path)}}):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.dotfiles import discover_bind_host

        reset_config()
        cfg = DevHelpersConfig()
        assert discover_bind_host(cfg) == "example.local"


def test_discover_port_env_beats_sidecar(monkeypatch, tmp_path):
    import sys

    monkeypatch.setenv("DEV_HELPERS_PORT", "1234")
    monkeypatch.setattr(sys, "argv", ["run-site", "run"])
    _write_min_sidecar(tmp_path, port=65359)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "dotfiles": {"directory": str(tmp_path)}}):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.dotfiles import discover_port

        reset_config()
        cfg = DevHelpersConfig()
        assert discover_port(cfg) == "1234"


def test_discover_port_argv_beats_sidecar(monkeypatch, tmp_path):
    """`runserver 9000` in argv must still win over the sidecar."""
    import sys

    monkeypatch.delenv("DEV_HELPERS_PORT", raising=False)
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver", "9000"])
    _write_min_sidecar(tmp_path, port=65359)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True, "dotfiles": {"directory": str(tmp_path)}}):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.dotfiles import discover_port

        reset_config()
        cfg = DevHelpersConfig()
        assert discover_port(cfg) == "9000"


def test_resolve_project_root_prefers_runsite_marker_over_inner_manage_py(tmp_path, monkeypatch):
    """src/-layout: manage.py in src/, runsite.toml at project root → root wins."""
    project = tmp_path / "proj"
    src = project / "src"
    src.mkdir(parents=True)
    (project / "runsite.toml").write_text("# run-site config\n", encoding="utf-8")
    (src / "manage.py").write_text("# django entry\n", encoding="utf-8")

    monkeypatch.delenv("DEV_HELPERS_PROJECT_ROOT", raising=False)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True}, BASE_DIR=str(src)):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.project_root import resolve_project_root

        reset_config()
        cfg = DevHelpersConfig()
        assert resolve_project_root(cfg) == project.resolve()


def test_resolve_project_root_run_site_config_marker(tmp_path, monkeypatch):
    """If only the runtime sidecar exists (no runsite.toml), still climb to it."""
    project = tmp_path / "proj"
    src = project / "src"
    src.mkdir(parents=True)
    (project / ".run-site-config").write_text("project_slug = 'x'\n", encoding="utf-8")
    (src / "manage.py").write_text("# django entry\n", encoding="utf-8")

    monkeypatch.delenv("DEV_HELPERS_PROJECT_ROOT", raising=False)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True}, BASE_DIR=str(src)):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.project_root import resolve_project_root

        reset_config()
        cfg = DevHelpersConfig()
        assert resolve_project_root(cfg) == project.resolve()


def test_resolve_project_root_fallback_unchanged_without_run_site(tmp_path, monkeypatch):
    """No run-site markers present → existing behavior (innermost manage.py)."""
    project = tmp_path / "proj"
    src = project / "src"
    src.mkdir(parents=True)
    (project / "pyproject.toml").write_text("# generic\n", encoding="utf-8")
    (src / "manage.py").write_text("# django entry\n", encoding="utf-8")

    monkeypatch.delenv("DEV_HELPERS_PROJECT_ROOT", raising=False)

    with override_settings(DJANGO_DEV_HELPERS={"enabled": True}, BASE_DIR=str(src)):
        from django_dev_helpers.conf import DevHelpersConfig, reset_config
        from django_dev_helpers.project_root import resolve_project_root

        reset_config()
        cfg = DevHelpersConfig()
        # Without a run-site marker, current behavior stops at innermost
        # generic marker (manage.py in src/).
        assert resolve_project_root(cfg) == src.resolve()
