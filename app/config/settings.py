import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENT = os.environ.get("APP_ENV", "development")
if ENVIRONMENT not in {"development", "production"}:
    raise ImproperlyConfigured("APP_ENV must be development or production")
PRODUCTION = ENVIRONMENT == "production"
DEBUG = not PRODUCTION
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only-not-for-production")
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver"
).split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split()
if PRODUCTION and (
    len(os.environ.get("DJANGO_SECRET_KEY", "")) < 50
    or "REPLACE" in SECRET_KEY
    or not os.environ.get("DJANGO_ALLOWED_HOSTS")
    or "*" in ALLOWED_HOSTS
    or not CSRF_TRUSTED_ORIGINS
    or any(not x.startswith("https://") for x in CSRF_TRUSTED_ORIGINS)
):
    raise ImproperlyConfigured(
        "Production requires SECRET_KEY, exact ALLOWED_HOSTS and HTTPS CSRF origins"
    )
RUNTIME = Path(os.environ.get("APP_RUNTIME", BASE_DIR / "runtime"))
RUNTIME.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("APP_DB", str(RUNTIME / "db.sqlite3")),
        "OPTIONS": {"timeout": 2, "transaction_mode": "IMMEDIATE"},
        "TEST": {"NAME": str(BASE_DIR / ".local" / "test.sqlite3")},
    }
}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "accounts",
    "questions",
    "learning",
    "operations",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.middleware.AccessMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.public_settings",
            ]
        },
    }
]
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"], "ip_address"]
AXES_RESET_ON_SUCCESS = False
AXES_CLIENT_IP_CALLABLE = "accounts.security.client_ip"
AXES_LOCKOUT_CALLABLE = "accounts.security.lockout"
AXES_SENSITIVE_PARAMETERS = ["username", "ip_address", "user_agent", "http_accept", "path_info"]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SECURE_SSL_REDIRECT = PRODUCTION
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if PRODUCTION else None
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = PRODUCTION
SECURE_HSTS_PRELOAD = PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "app/static_src"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = RUNTIME / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

SOURCE_URL = os.environ.get("SOURCE_URL", "")
