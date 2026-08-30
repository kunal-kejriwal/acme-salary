"""Scaffold smoke tests.

These assert the wiring the rest of the suite depends on: the test settings are
in force, every local app is installed, and pytest-django can actually hand out
a database. Deliberately minimal — real behaviour is tested per app.
"""

import pytest
from django.conf import settings


def test_test_settings_are_in_force():
    assert settings.SETTINGS_MODULE == "config.settings.test"
    assert settings.DEBUG is False


def test_local_apps_are_installed():
    for app in ("apps.core", "apps.employees", "apps.analytics"):
        assert app in settings.INSTALLED_APPS


def test_api_dependencies_are_installed():
    for app in ("rest_framework", "django_filters", "drf_spectacular", "corsheaders"):
        assert app in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_database_is_in_memory_sqlite():
    """The suite must not need Postgres (CLAUDE.md: fast, dependency-free)."""
    from django.db import connection

    assert connection.vendor == "sqlite"
