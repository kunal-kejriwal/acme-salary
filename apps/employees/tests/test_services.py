"""Employee service layer: salary normalisation and the audit trail.

The service is the only supported write path. These tests pin that down --
including the negative case that no signal or save() override is quietly
doing the audit write behind the service's back.
"""

from decimal import Decimal

import pytest

from apps.core.services import UnknownCurrencyError
from apps.employees.models import Employee, SalaryChange
from apps.employees.services import (
    create_employee,
    delete_employee,
    update_employee,
)


@pytest.fixture
def new_employee_attrs(employee_attrs):
    """Service input: no salary_usd -- the service computes it."""
    attrs = dict(employee_attrs)
    attrs.pop("salary_usd")
    return attrs


class TestCreateEmployee:
    def test_computes_salary_usd_from_the_local_amount(
        self, fx_rates, new_employee_attrs
    ):
        # 100000 INR * 0.012 = 1200.00
        employee = create_employee(
            **{**new_employee_attrs, "salary_amount": Decimal("100000.00")}
        )
        assert employee.salary_usd == Decimal("1200.00")

    def test_persists_the_normalised_amount(self, fx_rates, new_employee_attrs):
        employee = create_employee(
            **{**new_employee_attrs, "salary_amount": Decimal("100000.00")}
        )
        employee.refresh_from_db()
        assert employee.salary_usd == Decimal("1200.00")

    def test_usd_employee_normalises_to_the_same_figure(
        self, fx_rates, new_employee_attrs
    ):
        employee = create_employee(
            **{
                **new_employee_attrs,
                "salary_amount": Decimal("90000.00"),
                "currency": "USD",
            }
        )
        assert employee.salary_usd == Decimal("90000.00")

    def test_writes_no_audit_row(self, fx_rates, new_employee_attrs):
        """A starting salary is not a change.

        old_amount would have nothing truthful to hold, so hiring writes no
        history row.
        """
        create_employee(**new_employee_attrs)
        assert SalaryChange.objects.count() == 0

    def test_unknown_currency_raises_and_persists_nothing(
        self, fx_rates, new_employee_attrs
    ):
        with pytest.raises(UnknownCurrencyError):
            create_employee(**{**new_employee_attrs, "currency": "ZAR"})
        assert Employee.objects.count() == 0


class TestUpdateWritesAudit:
    def test_salary_raise_recomputes_salary_usd(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        employee.refresh_from_db()
        # 200000 INR * 0.012 = 2400.00
        assert employee.salary_usd == Decimal("2400.00")

    def test_salary_raise_appends_exactly_one_audit_row(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        assert employee.salary_changes.count() == 1

    def test_audit_row_records_both_amounts(self, fx_rates, employee):
        original = employee.salary_amount
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        change = employee.salary_changes.get()
        assert change.old_amount == original
        assert change.new_amount == Decimal("200000.00")

    def test_audit_row_records_who_made_the_change(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        assert employee.salary_changes.get().changed_by == "hr@acme.test"

    def test_currency_change_is_a_salary_change(self, fx_rates, employee):
        """The employee's pay in USD moves, so it belongs in the history."""
        update_employee(employee, currency="USD", changed_by="hr@acme.test")
        change = employee.salary_changes.get()
        assert change.old_currency == "INR"
        assert change.new_currency == "USD"

    def test_currency_change_recomputes_salary_usd(self, fx_rates, employee):
        update_employee(
            employee,
            salary_amount=Decimal("2000.00"),
            currency="USD",
            changed_by="hr@acme.test",
        )
        employee.refresh_from_db()
        assert employee.salary_usd == Decimal("2000.00")

    def test_successive_raises_accumulate(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        update_employee(
            employee, salary_amount=Decimal("300000.00"), changed_by="hr@acme.test"
        )
        assert employee.salary_changes.count() == 2

    def test_history_chains_old_to_new(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        update_employee(
            employee, salary_amount=Decimal("300000.00"), changed_by="hr@acme.test"
        )
        newest, older = employee.salary_changes.all()
        assert older.new_amount == newest.old_amount == Decimal("200000.00")


class TestUpdateWithoutSalaryChange:
    def test_editing_another_field_writes_no_audit_row(self, fx_rates, employee):
        update_employee(employee, department="Platform", changed_by="hr@acme.test")
        assert SalaryChange.objects.count() == 0

    def test_editing_another_field_still_saves(self, fx_rates, employee):
        update_employee(employee, department="Platform", changed_by="hr@acme.test")
        employee.refresh_from_db()
        assert employee.department == "Platform"

    def test_rewriting_the_same_salary_writes_no_audit_row(self, fx_rates, employee):
        """A no-op save must not pollute the trail with an empty change."""
        update_employee(
            employee, salary_amount=employee.salary_amount, changed_by="hr@acme.test"
        )
        assert SalaryChange.objects.count() == 0

    def test_equal_decimals_with_different_exponents_are_not_a_change(
        self, fx_rates, employee
    ):
        """2400000.00 and 2400000.0000 are the same salary."""
        update_employee(
            employee, salary_amount=Decimal("2400000.0000"), changed_by="hr@acme.test"
        )
        assert SalaryChange.objects.count() == 0


class TestAuditIsNotHiddenInTheModel:
    """The audit write belongs to the service, not to a signal or save().

    If someone moves it into a post_save receiver or a save() override, these
    fail -- which is the point. A hidden write path makes bulk_create silently
    skip the audit in Phase 5 and makes the trail impossible to reason about.
    """

    def test_direct_model_save_writes_no_audit_row(self, fx_rates, employee):
        employee.salary_amount = Decimal("999999.00")
        employee.save()
        assert SalaryChange.objects.count() == 0

    def test_queryset_update_writes_no_audit_row(self, fx_rates, employee):
        Employee.objects.filter(pk=employee.pk).update(
            salary_amount=Decimal("999999.00")
        )
        assert SalaryChange.objects.count() == 0


class TestUpdateAtomicity:
    def test_bad_currency_leaves_the_employee_untouched(self, fx_rates, employee):
        before = employee.salary_amount
        with pytest.raises(UnknownCurrencyError):
            update_employee(
                employee,
                salary_amount=Decimal("500000.00"),
                currency="ZAR",
                changed_by="hr@acme.test",
            )
        employee.refresh_from_db()
        assert employee.salary_amount == before

    def test_bad_currency_writes_no_audit_row(self, fx_rates, employee):
        with pytest.raises(UnknownCurrencyError):
            update_employee(
                employee,
                salary_amount=Decimal("500000.00"),
                currency="ZAR",
                changed_by="hr@acme.test",
            )
        assert SalaryChange.objects.count() == 0


class TestDeleteEmployee:
    def test_removes_the_employee(self, fx_rates, employee):
        delete_employee(employee)
        assert Employee.objects.count() == 0

    def test_removes_their_salary_history(self, fx_rates, employee):
        update_employee(
            employee, salary_amount=Decimal("200000.00"), changed_by="hr@acme.test"
        )
        delete_employee(employee)
        assert SalaryChange.objects.count() == 0
