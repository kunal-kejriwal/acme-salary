"""Fail-fast check for production configuration.

Kept as a pure function so it can be tested without importing a settings
module, which is awkward to do repeatedly in one process.
"""

from collections.abc import Iterable, Mapping

#: Everything production refuses to start without. Each of these is read with
#: no default on purpose -- see config/settings/prod.py.
REQUIRED_IN_PRODUCTION = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "DATABASE_URL",
)


def missing_settings(
    environ: Mapping[str, str], names: Iterable[str] = REQUIRED_IN_PRODUCTION
) -> list[str]:
    """Names that are absent or blank, in the order given.

    Blank counts as missing: an environment variable set to an empty string is
    a configuration mistake, not a value.
    """
    return [name for name in names if not environ.get(name, "").strip()]


def describe_missing(names: list[str]) -> str:
    """The message an operator sees when a deploy is misconfigured.

    Lists everything missing at once. Reporting them one at a time turns a
    single fix into one failed deploy per variable.
    """
    listed = "\n".join(f"  - {name}" for name in names)
    return (
        f"Cannot start: {len(names)} required environment "
        f"variable{'s are' if len(names) > 1 else ' is'} missing.\n\n"
        f"{listed}\n\n"
        "Set them on the service and redeploy. Generate a secret key with:\n"
        '  python -c "from django.core.management.utils import '
        'get_random_secret_key as k; print(k())"\n'
        "See the Deployment section of README.md for the full list."
    )
