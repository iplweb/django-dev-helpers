from __future__ import annotations

import importlib
import json
import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run diagnostics for django-dev-helpers setup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-services",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--json",
            dest="output_json",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **options):
        from django.core.exceptions import ImproperlyConfigured

        from django_dev_helpers.conf import get_config

        skip_services = options["skip_services"]
        output_json = options["output_json"]

        checks: list[dict] = []

        self._check_config_dict(checks)

        cfg = None
        try:
            cfg = get_config()
        except ImproperlyConfigured as exc:
            checks.append({
                "name": "Config",
                "status": "error",
                "message": str(exc),
            })

        if cfg is not None:
            self._check_activation(cfg, checks)
            self._check_autologin_config(cfg, checks)
            self._check_user_exists(cfg, checks)
            if not skip_services:
                self._check_db_reachable(checks)
                self._check_redis_reachable(cfg, checks)
            self._check_token_env(checks)
            self._check_dotfile_dir_writable(cfg, checks)
            self._check_gitignore(cfg, checks)
            self._check_allowed_hosts(checks)
            self._check_secret_key(checks)
            self._check_legacy_run_site_dotfiles(cfg, checks)
            self._check_sidecar(cfg, checks)

        has_errors = any(c["status"] == "error" for c in checks)
        has_warnings = any(c["status"] == "warning" for c in checks)

        if output_json:
            status = "ok"
            if has_errors:
                status = "error"
            elif has_warnings:
                status = "warning"
            self.stdout.write(json.dumps({"status": status, "checks": checks}, indent=2))
        else:
            for check in checks:
                icon = {"ok": "✓", "warning": "⚠", "error": "✗"}[check["status"]]
                line = f"  [{icon}] {check['name']}"
                if check.get("message"):
                    line += f": {check['message']}"
                self.stdout.write(line)

        if has_errors:
            sys.exit(1)
        if has_warnings:
            sys.exit(2)

    def _check_config_dict(self, checks: list[dict]) -> None:
        raw = getattr(settings, "DJANGO_DEV_HELPERS", None)
        if raw is None:
            checks.append({"name": "Config dict", "status": "ok", "message": "not set (using defaults)"})
        elif not isinstance(raw, dict):
            checks.append({
                "name": "Config dict",
                "status": "error",
                "message": "DJANGO_DEV_HELPERS must be a dict",
            })
        else:
            known_keys = {
                "enabled", "autologin", "dotfiles", "agent_help",
                "browser_open", "gitignore", "lookup", "safety",
            }
            unknown = set(raw.keys()) - known_keys
            if unknown:
                checks.append({
                    "name": "Config dict",
                    "status": "warning",
                    "message": f"unknown keys: {', '.join(sorted(unknown))}",
                })
            else:
                checks.append({"name": "Config dict", "status": "ok", "message": None})

    def _check_activation(self, cfg, checks: list[dict]) -> None:
        active = cfg.is_active()
        if not active:
            checks.append({
                "name": "Activation",
                "status": "error",
                "message": "not active; set DJANGO_DEV_HELPERS_ENABLED=1 or enabled=True",
            })
        elif not settings.DEBUG:
            checks.append({
                "name": "Activation",
                "status": "error",
                "message": "active but DEBUG=False (unsafe)",
            })
        else:
            checks.append({"name": "Activation", "status": "ok", "message": None})

    def _check_autologin_config(self, cfg, checks: list[dict]) -> None:
        if not cfg.autologin.enabled:
            checks.append({"name": "Autologin config", "status": "ok", "message": "disabled"})
            return

        issues: list[str] = []
        field = cfg.autologin.user_lookup_field
        if not field:
            issues.append("user_lookup_field is empty")

        value = cfg.autologin.user_lookup_value
        if not value:
            issues.append("user_lookup_value is empty")

        backend = cfg.autologin.auth_backend
        try:
            module_path, _, attr = backend.rpartition(".")
            if not module_path:
                raise ImportError(backend)
            mod = importlib.import_module(module_path)
            getattr(mod, attr)
        except (ImportError, AttributeError):
            issues.append(f"auth_backend '{backend}' is not importable")

        if issues:
            checks.append({
                "name": "Autologin config",
                "status": "error",
                "message": "; ".join(issues),
            })
        else:
            checks.append({"name": "Autologin config", "status": "ok", "message": None})

    def _check_user_exists(self, cfg, checks: list[dict]) -> None:
        if not cfg.autologin.enabled:
            return
        try:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            lookup = {cfg.autologin.user_lookup_field: cfg.autologin.user_lookup_value}
            User.objects.get(**lookup)
            checks.append({"name": "Autologin user", "status": "ok", "message": None})
        except User.DoesNotExist:
            checks.append({
                "name": "Autologin user",
                "status": "error",
                "message": (
                    f"user with {cfg.autologin.user_lookup_field}="
                    f"'{cfg.autologin.user_lookup_value}' not found"
                ),
            })
        except Exception as exc:
            checks.append({
                "name": "Autologin user",
                "status": "warning",
                "message": f"could not query: {exc}",
            })

    def _check_db_reachable(self, checks: list[dict]) -> None:
        try:
            from django.db import connection

            connection.ensure_connection()
            checks.append({"name": "Database", "status": "ok", "message": None})
        except Exception as exc:
            checks.append({
                "name": "Database",
                "status": "error",
                "message": str(exc),
            })

    def _check_redis_reachable(self, cfg, checks: list[dict]) -> None:
        from django_dev_helpers.dotfiles import resolve_redis_endpoint

        endpoint = resolve_redis_endpoint(cfg)
        if endpoint is None:
            checks.append({
                "name": "Redis",
                "status": "ok",
                "message": "not configured (skipped)",
            })
            return

        host, port = endpoint
        try:
            import socket

            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            checks.append({"name": "Redis", "status": "ok", "message": f"{host}:{port}"})
        except Exception as exc:
            checks.append({
                "name": "Redis",
                "status": "warning",
                "message": f"{host}:{port} unreachable: {exc}",
            })

    def _check_token_env(self, checks: list[dict]) -> None:
        from django_dev_helpers.tokens import ENV_VAR

        token = os.environ.get(ENV_VAR)
        if not token:
            checks.append({
                "name": "Token env var",
                "status": "warning",
                "message": f"{ENV_VAR} is not set",
            })
        elif len(token) < 20:
            checks.append({
                "name": "Token env var",
                "status": "warning",
                "message": f"token is short ({len(token)} chars)",
            })
        else:
            checks.append({"name": "Token env var", "status": "ok", "message": None})

    def _check_dotfile_dir_writable(self, cfg, checks: list[dict]) -> None:
        try:
            from django_dev_helpers.project_root import resolve_project_root

            root = resolve_project_root(cfg)
            if not os.access(root, os.W_OK):
                checks.append({
                    "name": "Dotfile dir",
                    "status": "error",
                    "message": f"{root} is not writable",
                })
            else:
                checks.append({"name": "Dotfile dir", "status": "ok", "message": str(root)})
        except Exception as exc:
            checks.append({
                "name": "Dotfile dir",
                "status": "error",
                "message": str(exc),
            })

    def _check_gitignore(self, cfg, checks: list[dict]) -> None:
        try:
            from django_dev_helpers.gitignore import get_gitignore_path, get_missing_entries

            gitignore_path = get_gitignore_path(cfg)
            if not gitignore_path.exists():
                checks.append({
                    "name": ".gitignore",
                    "status": "warning",
                    "message": f".gitignore not found at {gitignore_path}",
                })
                return
            content = gitignore_path.read_text()
            missing = get_missing_entries(content, cfg)
            if missing:
                checks.append({
                    "name": ".gitignore",
                    "status": "warning",
                    "message": f"missing entries: {', '.join(missing)}",
                })
            else:
                checks.append({"name": ".gitignore", "status": "ok", "message": None})
        except ImportError:
            checks.append({
                "name": ".gitignore",
                "status": "warning",
                "message": "gitignore module not available",
            })
        except Exception as exc:
            checks.append({
                "name": ".gitignore",
                "status": "warning",
                "message": str(exc),
            })

    def _check_allowed_hosts(self, checks: list[dict]) -> None:
        _localhost = {"localhost", "127.0.0.1", "*"}
        non_local = [h for h in settings.ALLOWED_HOSTS if h not in _localhost]
        if non_local:
            checks.append({
                "name": "ALLOWED_HOSTS",
                "status": "warning",
                "message": f"non-localhost entries: {', '.join(non_local)}",
            })
        else:
            checks.append({"name": "ALLOWED_HOSTS", "status": "ok", "message": None})

    def _check_secret_key(self, checks: list[dict]) -> None:
        key = settings.SECRET_KEY
        if len(key) >= 50 and not key.startswith("django-insecure-"):
            checks.append({
                "name": "SECRET_KEY",
                "status": "warning",
                "message": "looks like a production secret (length >= 50, no django-insecure- prefix)",
            })
        else:
            checks.append({"name": "SECRET_KEY", "status": "ok", "message": None})

    def _check_legacy_run_site_dotfiles(self, cfg, checks: list[dict]) -> None:
        try:
            from django_dev_helpers.project_root import resolve_project_root

            root = resolve_project_root(cfg)
        except Exception as exc:
            checks.append({
                "name": "Legacy .run_site_* dotfiles",
                "status": "warning",
                "message": f"could not resolve project root: {exc}",
            })
            return
        legacy = sorted(p.name for p in root.glob(".run_site_*"))
        if legacy:
            checks.append({
                "name": "Legacy .run_site_* dotfiles",
                "status": "warning",
                "message": (
                    f"found {len(legacy)} legacy file(s) ({', '.join(legacy)}); "
                    "these are leftovers from the run_site management command and "
                    "are superseded by .dev_helpers_*. Safe to delete."
                ),
            })
        else:
            checks.append({
                "name": "Legacy .run_site_* dotfiles",
                "status": "ok",
                "message": None,
            })

    def _check_sidecar(self, cfg, checks: list[dict]) -> None:
        try:
            from django_dev_helpers import sidecar
            from django_dev_helpers.project_root import resolve_project_root

            root = resolve_project_root(cfg)
        except Exception as exc:
            checks.append({
                "name": "run-site sidecar",
                "status": "warning",
                "message": f"could not resolve project root: {exc}",
            })
            return

        path = sidecar.sidecar_path(root)
        if not path.exists():
            checks.append({
                "name": "run-site sidecar",
                "status": "ok",
                "message": "no .run-site-config (standalone or run-site not started)",
            })
            return

        data = sidecar.read_sidecar(root)
        if data is None:
            checks.append({
                "name": "run-site sidecar",
                "status": "warning",
                "message": f"{path} exists but could not be parsed",
            })
            return

        endpoints = sidecar.extract_endpoints(data)
        summary_bits = []
        if "pg_host" in endpoints and "pg_port" in endpoints:
            summary_bits.append(f"pg={endpoints['pg_host']}:{endpoints['pg_port']}")
        if "redis_host" in endpoints and "redis_port" in endpoints:
            summary_bits.append(f"redis={endpoints['redis_host']}:{endpoints['redis_port']}")
        checks.append({
            "name": "run-site sidecar",
            "status": "ok",
            "message": f"{path.name} ({', '.join(summary_bits) or 'parsed'})",
        })
