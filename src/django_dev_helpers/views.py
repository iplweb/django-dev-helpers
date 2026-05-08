import hmac
import os

from django.contrib.auth import get_user_model, login
from django.http import Http404, HttpResponseRedirect
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def autologin(request):
    from .conf import get_config

    cfg = get_config()
    cfg.refuse_if_inactive()
    cfg.refuse_if_unsafe_host(request)

    expected = os.environ.get("DEV_HELPERS_AUTOLOGIN_TOKEN")
    if not expected:
        raise Http404()

    provided = request.GET.get("token") or ""
    if not hmac.compare_digest(expected, provided):
        raise Http404()

    User = get_user_model()
    try:
        user = User.objects.get(**{cfg.autologin.user_lookup_field: cfg.autologin.user_lookup_value})
    except User.DoesNotExist as exc:
        raise Http404() from exc
    except User.MultipleObjectsReturned as exc:
        raise Http404() from exc

    login(request, user, backend=cfg.autologin.auth_backend)

    if cfg.autologin.flash_message:
        from django.contrib import messages

        messages.success(request, cfg.autologin.flash_message)

    response = HttpResponseRedirect(cfg.autologin.redirect_to)

    for cookie in cfg.autologin.extra_cookies:
        kwargs = dict(cookie)
        if "name" in kwargs and "key" not in kwargs:
            kwargs["key"] = kwargs.pop("name")
        response.set_cookie(**kwargs)

    return response
