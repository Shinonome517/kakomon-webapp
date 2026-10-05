from django.conf import settings


def public_settings(request):
    return {"source_url": settings.SOURCE_URL}
