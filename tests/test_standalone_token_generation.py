import os


def test_init_token_generates():
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)
    from django_dev_helpers.tokens import init_token

    token = init_token()
    assert token
    assert len(token) > 20
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_init_token_reuses_existing():
    os.environ["DEV_HELPERS_AUTOLOGIN_TOKEN"] = "existing-token"
    from django_dev_helpers.tokens import init_token

    token = init_token()
    assert token == "existing-token"
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_token_in_env_after_init():
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)
    from django_dev_helpers.tokens import init_token

    init_token()
    assert os.environ.get("DEV_HELPERS_AUTOLOGIN_TOKEN") is not None
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)


def test_current_token_returns_none():
    os.environ.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)
    from django_dev_helpers.tokens import current_token

    assert current_token() is None
