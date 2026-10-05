from django.conf import settings
from django.shortcuts import render


def client_ip(request):
    # Production port is loopback-only; Nginx must overwrite this header.
    return (
        request.META.get("HTTP_X_VERIFIED_CLIENT_IP")
        if settings.PRODUCTION
        else request.META.get("REMOTE_ADDR")
    )


def lockout(request, credentials=None, *args, **kwargs):
    return render(request, "locked.html", status=429)
