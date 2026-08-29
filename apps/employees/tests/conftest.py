"""Fixtures for the employees suite."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.employees.models import Employee

#: Model-level defaults. salary_usd is supplied explicitly because the model
#: does not compute it -- that is the service layer's job.
EMPLOYEE_DEFAULTS = {
    "employee_code": "ACME-0001",
    "first_name": "Asha",
    "last_name": "Rao",
    "department": "Engineering",
    "country": "IN",
    "joined_on": dt.date(2021, 4, 1),
    "salary_amount": Decimal("2400000.00"),
    "currency": "INR",
    "salary_usd": Decimal("28800.00"),
}


@pytest.fixture
def employee_attrs():
    return dict(EMPLOYEE_DEFAULTS)


@pytest.fixture
def make_employee(db):
    """Create an Employee straight through the ORM, bypassing the service.

    Model tests use this deliberately: it is the only way to assert what the
    database itself enforces.
    """

    def _make(**overrides):
        return Employee.objects.create(**{**EMPLOYEE_DEFAULTS, **overrides})

    return _make


@pytest.fixture
def employee(make_employee):
    return make_employee()
