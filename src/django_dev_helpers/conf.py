from __future__ import annotations

import fnmatch
import os
import types
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.http.request import split_domain_port

_AUTOLOGIN_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "user_lookup_field": "username",
    "user_lookup_value": "admin",
    "url_path": "__autologin__/",
    "redirect_to": "/",
    "auth_backend": "django.contrib.auth.backends.ModelBackend",
    "flash_message": "",
    "extra_cookies": [],
    "allowed_hosts": [],
}

_DOTFILES_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "directory": None,
    "token_filename": ".dev_helpers_token",
    "port_filename": ".dev_helpers_port",
    "pg_port_filename": ".dev_helpers_pg_port",
    "pg_host_filename": ".dev_helpers_pg_host",
    "redis_port_filename": ".dev_helpers_redis_port",
    "redis_host_filename": ".dev_helpers_redis_host",
    "token_chmod": 0o600,
}

_AGENT_HELP_DEFAULTS: dict[str, Any] = {
    "auto_print": True,
    "template": None,
    "display_host": None,
    "show_db_credentials": True,
}

_BROWSER_OPEN_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "url_path": None,
    "probe_path": "/admin/login/",
    "probe_timeout_seconds": 30.0,
}

_GITIGNORE_DEFAULTS: dict[str, Any] = {
    "mode": "warn",
    "path": None,
}

_LOOKUP_DEFAULTS: dict[str, Any] = {
    "source": "auto",
    "callable": None,
}

_SAFETY_DEFAULTS: dict[str, Any] = {
    "non_serving_commands": [],
}

_DEFAULTS: dict[str, Any] = {
    "enabled": None,
    "autologin": _AUTOLOGIN_DEFAULTS,
    "dotfiles": _DOTFILES_DEFAULTS,
    "agent_help": _AGENT_HELP_DEFAULTS,
    "browser_open": _BROWSER_OPEN_DEFAULTS,
    "gitignore": _GITIGNORE_DEFAULTS,
    "lookup": _LOOKUP_DEFAULTS,
    "safety": _SAFETY_DEFAULTS,
}

_VALID_GITIGNORE_MODES = {"warn", "auto-add", "error", "off"}
_VALID_LOOKUP_SOURCES = {"auto", "env", "settings", "sidecar"}
_KNOWN_TOP_LEVEL_KEYS = set(_DEFAULTS.keys())


def _merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _dict_to_namespace(d: dict[str, Any]) -> types.SimpleNamespace:
    ns = types.SimpleNamespace()
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(ns, key, _dict_to_namespace(value))
        else:
            setattr(ns, key, value)
    return ns


def _validate(merged: dict[str, Any], raw: dict[str, Any]) -> None:
    unknown = set(raw.keys()) - _KNOWN_TOP_LEVEL_KEYS
    if unknown:
        raise ImproperlyConfigured(
            f"DJANGO_DEV_HELPERS: unknown top-level keys: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_TOP_LEVEL_KEYS)}."
        )

    gi_mode = merged["gitignore"]["mode"]
    if gi_mode not in _VALID_GITIGNORE_MODES:
        raise ImproperlyConfigured(
            f"DJANGO_DEV_HELPERS['gitignore']['mode']={gi_mode!r} is not valid. "
            f"Choose one of: {sorted(_VALID_GITIGNORE_MODES)}."
        )

    lk_source = merged["lookup"]["source"]
    if lk_source not in _VALID_LOOKUP_SOURCES:
        raise ImproperlyConfigured(
            f"DJANGO_DEV_HELPERS['lookup']['source']={lk_source!r} is not valid. "
            f"Choose one of: {sorted(_VALID_LOOKUP_SOURCES)}."
        )

    extra_cookies = merged["autologin"]["extra_cookies"]
    if not isinstance(extra_cookies, (list, tuple)):
        raise ImproperlyConfigured(
            "DJANGO_DEV_HELPERS['autologin']['extra_cookies'] must be a list of dicts."
        )
    for i, cookie in enumerate(extra_cookies):
        if not isinstance(cookie, dict):
            raise ImproperlyConfigured(
                f"DJANGO_DEV_HELPERS['autologin']['extra_cookies'][{i}] must be a dict."
            )

    allowed = merged["autologin"]["allowed_hosts"]
    if not isinstance(allowed, (list, tuple)):
        raise ImproperlyConfigured(
            "DJANGO_DEV_HELPERS['autologin']['allowed_hosts'] must be a list of strings."
        )

    non_serving = merged["safety"]["non_serving_commands"]
    if not isinstance(non_serving, (list, tuple, set, frozenset)):
        raise ImproperlyConfigured(
            "DJANGO_DEV_HELPERS['safety']['non_serving_commands'] must be a list/set of strings."
        )

    callable_spec = merged["lookup"]["callable"]
    if callable_spec is not None and not isinstance(callable_spec, str):
        raise ImproperlyConfigured(
            "DJANGO_DEV_HELPERS['lookup']['callable'] must be a 'module.path:attr' string or None."
        )


def _apply_env_overrides(merged: dict[str, Any], raw: dict[str, Any]) -> None:
    """Pull a small set of orchestrator-set env vars into merged config.

    Currently only DEV_HELPERS_AUTOLOGIN_USERNAME, applied as the autologin
    user lookup value when the user has not explicitly set it.
    """
    raw_autologin = raw.get("autologin") or {}
    if "user_lookup_value" not in raw_autologin:
        env_user = os.environ.get("DEV_HELPERS_AUTOLOGIN_USERNAME")
        if env_user:
            merged["autologin"]["user_lookup_value"] = env_user


class DevHelpersConfig:
    def __init__(self) -> None:
        raw: dict[str, Any] = getattr(settings, "DJANGO_DEV_HELPERS", {}) or {}
        if not isinstance(raw, dict):
            raise ImproperlyConfigured("DJANGO_DEV_HELPERS must be a dict.")
        merged = _merge(_DEFAULTS, raw)
        _validate(merged, raw)
        _apply_env_overrides(merged, raw)
        self.enabled = merged["enabled"]
        self.autologin = _dict_to_namespace(merged["autologin"])
        self.dotfiles = _dict_to_namespace(merged["dotfiles"])
        self.agent_help = _dict_to_namespace(merged["agent_help"])
        self.browser_open = _dict_to_namespace(merged["browser_open"])
        self.gitignore = _dict_to_namespace(merged["gitignore"])
        self.lookup = _dict_to_namespace(merged["lookup"])
        self.safety = _dict_to_namespace(merged["safety"])

    def is_active(self) -> bool:
        if self.enabled is False:
            return False
        if self.enabled is True:
            return True
        return os.environ.get("DJANGO_DEV_HELPERS_ENABLED") == "1"

    def refuse_if_inactive(self) -> None:
        if not self.is_active():
            raise Http404()

    def refuse_if_unsafe_host(self, request: Any) -> None:
        hostname, _ = split_domain_port(request.get_host())
        if hostname is None:
            raise Http404()
        hostname = hostname.lower()
        default_allow = {"localhost", "127.0.0.1", "[::1]"}
        if hostname in default_allow:
            return
        extra_allow = self.autologin.allowed_hosts or []
        if not any(
            fnmatch.fnmatchcase(hostname, pat.lower()) for pat in extra_allow
        ):
            raise Http404()


_config: DevHelpersConfig | None = None


def get_config() -> DevHelpersConfig:
    global _config
    if _config is None:
        _config = DevHelpersConfig()
    return _config


def reset_config() -> None:
    global _config
    _config = None
