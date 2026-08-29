"""Production: everything deployment-shaped comes from the environment."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

DATABASES = {"default": env.db_url("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

# JSON only — no browsable API in production.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
]

# Assumes TLS termination at the platform edge (Railway), which sets
# X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
X_FRAME_OPTIONS = "DENY"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}
