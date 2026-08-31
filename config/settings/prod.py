"""Production: everything deployment-shaped comes from the environment."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env
from .required import describe_missing, missing_settings

DEBUG = False

# Check every requirement before reading any of them. Each env() call below
# raises on its own, which would report exactly one missing variable per
# failed deploy; this names them all at once.
_missing = missing_settings(os.environ)
if _missing:
    raise ImproperlyConfigured(describe_missing(_missing))

# No default, deliberately: a misconfigured deploy fails at boot rather than
# running on the insecure development key.
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

DATABASES = {"default": env.db_url("DATABASE_URL")}

# WhiteNoise serves the admin's CSS and JS straight from the app process.
# It has to sit directly after SecurityMiddleware.
MIDDLEWARE = MIDDLEWARE.copy()  # noqa: F405
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
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
# Lax, not None. The SPA reaches the API through a same-origin proxy, so
# these cookies are first-party and never travel cross-site. SameSite=None
# would be strictly weaker for no benefit -- and it is a losing position
# regardless, since browsers are removing third-party cookies entirely.
# Still environment-driven, so a deployment that genuinely needs cross-site
# can set it without a code change.
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
X_FRAME_OPTIONS = "DENY"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Hashed filenames plus gzip/brotli, produced by collectstatic.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
