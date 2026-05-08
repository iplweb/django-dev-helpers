import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings


def _run_doctor(json_output: bool = True) -> tuple[int, str]:
    out = StringIO()
    args = ["dev_helpers_doctor", "--skip-services"]
    if json_output:
        args.append("--json")
    try:
        call_command(*args, stdout=out)
    except SystemExit as exc:
        return int(exc.code or 0), out.getvalue()
    return 0, out.getvalue()


@pytest.mark.django_db
def test_doctor_invalid_enum_value_emits_config_error_in_json():
    with override_settings(DJANGO_DEV_HELPERS={"gitignore": {"mode": "bogus"}}):
        code, output = _run_doctor(json_output=True)

    assert code == 1, output
    payload = json.loads(output)
    assert payload["status"] == "error"
    config_checks = [c for c in payload["checks"] if c["name"] == "Config"]
    assert len(config_checks) == 1
    assert config_checks[0]["status"] == "error"
    assert "bogus" in config_checks[0]["message"]
    # Subsequent cfg-dependent checks must be skipped to avoid crashing on cfg=None.
    skipped_names = {"Activation", "Autologin config", ".gitignore"}
    present = {c["name"] for c in payload["checks"]}
    assert not (skipped_names & present)


@pytest.mark.django_db
def test_doctor_non_dict_settings_emits_structured_error():
    with override_settings(DJANGO_DEV_HELPERS="not a dict"):
        code, output = _run_doctor(json_output=True)

    assert code == 1, output
    payload = json.loads(output)
    assert payload["status"] == "error"
    names_to_statuses = {c["name"]: c["status"] for c in payload["checks"]}
    # _check_config_dict produces its own error for non-dict settings.
    assert names_to_statuses.get("Config dict") == "error"
    # get_config() also raises ImproperlyConfigured, which the handler catches.
    assert names_to_statuses.get("Config") == "error"


@pytest.mark.django_db
def test_doctor_unknown_top_level_key_emits_config_error():
    # Unknown keys cause both a warning from _check_config_dict and an
    # ImproperlyConfigured from DevHelpersConfig (which validates strictly).
    with override_settings(DJANGO_DEV_HELPERS={"unknown_key": 1}):
        code, output = _run_doctor(json_output=True)

    assert code == 1, output
    payload = json.loads(output)
    config_check = next(c for c in payload["checks"] if c["name"] == "Config")
    assert config_check["status"] == "error"
    assert "unknown_key" in config_check["message"]


@pytest.mark.django_db
def test_doctor_text_output_invalid_config_does_not_crash():
    with override_settings(DJANGO_DEV_HELPERS={"gitignore": {"mode": "bogus"}}):
        code, output = _run_doctor(json_output=False)

    assert code == 1
    assert "Config" in output
