from django.urls import path


def autologin_urlpatterns():
    from .conf import get_config

    cfg = get_config()
    if not cfg.is_active() or not cfg.autologin.enabled:
        return []
    from . import views

    return [
        path(cfg.autologin.url_path, views.autologin, name="dev_helpers_autologin"),
    ]
