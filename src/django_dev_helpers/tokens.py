import os
import secrets

ENV_VAR = "DEV_HELPERS_AUTOLOGIN_TOKEN"
TOKEN_BYTES = 32

def init_token() -> str:
    existing = os.environ.get(ENV_VAR)
    if existing:
        return existing
    token = secrets.token_urlsafe(TOKEN_BYTES)
    os.environ[ENV_VAR] = token
    return token

def current_token() -> str | None:
    return os.environ.get(ENV_VAR)
