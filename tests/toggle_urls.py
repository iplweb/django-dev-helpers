"""Helper urlconf for toggle tests: echoes auth state and GET keys."""

from django.http import HttpResponse
from django.urls import path


def whoami(request):
    return HttpResponse(b"authenticated" if request.user.is_authenticated else b"anonymous")


def echo(request):
    return HttpResponse(",".join(sorted(request.GET.keys())).encode())


urlpatterns = [
    path("whoami/", whoami),
    path("echo/", echo),
]
