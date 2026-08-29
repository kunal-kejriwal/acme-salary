"""Test settings: in-memory SQLite, no external dependencies, fast hashing.

The suite must stay under 10 seconds (CLAUDE.md), so this deliberately avoids
Postgres. Percentile analytics therefore need a portable expression — see
docs/DECISIONS.md.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Fast, deliberately weak hashing — test fixtures only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Migrations still run so model/migration drift is caught by the suite.
