"""Fixtures shared across every app's test suite."""

import pytest
from django.core.management import call_command


@pytest.fixture
def fx_rates(db):
    """Load the in-repo FX rate table.

    Anything that converts money needs these rows, so employees, imports and
    analytics all depend on this fixture too.
    """
    call_command("loaddata", "fx_rates", verbosity=0)
