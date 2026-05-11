"""URLconf with no autologin URL wired -- used to exercise the middleware path.

Includes a single no-op route so Django's URL resolver actually uses this
urlconf instead of falling back to the built-in "welcome" page (which it
does when ``urlpatterns`` is empty, and which would mask the assertion
that the middleware ignores non-autologin paths).
"""

from django.http import HttpResponse
from django.urls import path


def _noop(request):
    return HttpResponse("noop")


urlpatterns = [
    path("_noop/", _noop),
]
