"""Fixtures shared across every app's test suite."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture
def fx_rates(db):
    """Load the in-repo FX rate table.

    Anything that converts money needs these rows, so employees, imports and
    analytics all depend on this fixture too.
    """
    call_command("loaddata", "fx_rates", verbosity=0)


@pytest.fixture
def hr_user(db):
    """The single HR manager persona (ARCHITECTURE.md section 8)."""
    return get_user_model().objects.create_user(
        username="hr@acme.test",
        email="hr@acme.test",
        password="not-a-real-password",
    )


@pytest.fixture
def anonymous_client():
    return APIClient()


@pytest.fixture
def api_client(hr_user):
    """An authenticated client. The API denies anonymous access by default."""
    client = APIClient()
    client.force_authenticate(user=hr_user)
    return client
