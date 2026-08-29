"""Business logic for the employees app.

Views stay thin; everything testable lives here (CLAUDE.md, "thin views, fat
services").

This module is the only supported write path for employees. Two invariants it
owns, deliberately kept out of the model:

1. `salary_usd` is recomputed from `core.to_usd` whenever pay changes.
2. Every salary movement appends a `SalaryChange` row.

Neither is a signal or a `save()` override. That is a design choice, not an
oversight -- a hidden write path would fire on fixtures and migrations, would
silently do nothing under `bulk_create` (which Phase 5 needs), and would make
the audit trail impossible to follow from the call site. Keeping it explicit
means the one place that changes pay is the one place that records it.
"""

from decimal import Decimal

from django.db import transaction

from apps.core.services import to_usd
from apps.employees.models import Employee, SalaryChange


def create_employee(
    *, salary_amount: Decimal, currency: str, **fields
) -> Employee:
    """Create an employee, normalising their salary to USD.

    No audit row: a starting salary is not a change, and `old_amount` would
    have nothing truthful to hold.

    Raises UnknownCurrencyError or MissingRateError before anything is
    written, so a bad currency leaves no partial row behind.
    """
    salary_usd = to_usd(salary_amount, currency)
    return Employee.objects.create(
        salary_amount=salary_amount,
        currency=currency,
        salary_usd=salary_usd,
        **fields,
    )


@transaction.atomic
def update_employee(employee: Employee, *, changed_by: str, **fields) -> Employee:
    """Apply `fields` to `employee`, auditing any change to pay.

    `changed_by` is required rather than defaulted: if pay moves, the trail
    has to say who moved it.

    A salary change means a different amount *or* a different currency --
    both move what the employee is actually paid. Decimal comparison is
    numeric, so 2400000.00 and 2400000.0000 are correctly not a change.
    """
    old_amount = employee.salary_amount
    old_currency = employee.currency

    new_amount = fields.pop("salary_amount", old_amount)
    new_currency = fields.pop("currency", old_currency)

    salary_changed = new_amount != old_amount or new_currency != old_currency

    for field, value in fields.items():
        setattr(employee, field, value)

    if salary_changed:
        # Computed before any write, so an unknown currency aborts the whole
        # update rather than leaving pay and salary_usd out of step.
        employee.salary_usd = to_usd(new_amount, new_currency)
        employee.salary_amount = new_amount
        employee.currency = new_currency

    employee.save()

    if salary_changed:
        SalaryChange.objects.create(
            employee=employee,
            old_amount=old_amount,
            old_currency=old_currency,
            new_amount=new_amount,
            new_currency=new_currency,
            changed_by=changed_by,
        )

    return employee


def delete_employee(employee: Employee) -> None:
    """Remove an employee and, by cascade, their salary history.

    A single call site for deletion, so a future move to soft-delete or a
    retention policy has an obvious home.
    """
    employee.delete()
