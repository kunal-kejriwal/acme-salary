"""Local development: SQLite by default, browsable API, CORS for the Vite server.

The database comes from base.py, which falls back to a local SQLite file when
DATABASE_URL is unset — the project runs with no external services. Set
DATABASE_URL to run against Postgres, which is what production uses.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# The Vite dev server.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)

# Browsable API is a genuine convenience while building against the endpoints.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]
