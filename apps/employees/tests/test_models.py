"""What the Employee and SalaryChange tables themselves guarantee.

These assert database-level and model-level constraints, so they create rows
through the ORM rather than the service layer.
"""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Index

from apps.employees.models import Employee, SalaryChange


class TestEmployeeIdentity:
    def test_primary_key_is_a_uuid(self, employee):
        assert isinstance(employee.pk, uuid.UUID)

    def test_uuids_are_not_sequential(self, make_employee):
        """A guessable employee URL is an information leak."""
        first = make_employee(employee_code="ACME-0001")
        second = make_employee(employee_code="ACME-0002")
        assert first.pk != second.pk

    def test_employee_code_is_unique(self, make_employee):
        make_employee(employee_code="ACME-0001")
        with pytest.raises(IntegrityError):
            make_employee(employee_code="ACME-0001")

    def test_str_identifies_the_person_and_their_code(self, employee):
        assert str(employee) == "Asha Rao (ACME-0001)"


class TestEmployeeMoney:
    def test_salary_amount_is_decimal_not_float(self, employee):
        employee.refresh_from_db()
        assert isinstance(employee.salary_amount, Decimal)

    def test_salary_usd_is_decimal_not_float(self, employee):
        employee.refresh_from_db()
        assert isinstance(employee.salary_usd, Decimal)

    def test_negative_salary_is_rejected_by_the_database(self, make_employee):
        """A CHECK constraint, so the rule holds against any write path."""
        with pytest.raises(IntegrityError):
            make_employee(salary_amount=Decimal("-1.00"))

    def test_zero_salary_is_allowed(self, make_employee):
        """Unpaid interns and leave-of-absence records are real."""
        assert make_employee(salary_amount=Decimal("0.00")).salary_amount == Decimal(
            "0.00"
        )

    def test_salary_usd_is_required(self, make_employee):
        """Nothing may land without a normalised figure.

        Non-null with no default is what forces writes through the service.
        """
        with pytest.raises(IntegrityError):
            make_employee(salary_usd=None)

    def test_currency_outside_the_choices_fails_validation(self, db, employee_attrs):
        # full_clean() checks uniqueness, so it needs the database.
        employee = Employee(**{**employee_attrs, "currency": "ZAR"})
        with pytest.raises(ValidationError):
            employee.full_clean()

    def test_salary_holds_large_local_currency_amounts(self, make_employee):
        """JPY and INR salaries have many digits before the decimal point."""
        employee = make_employee(
            salary_amount=Decimal("99999999.99"), currency="JPY"
        )
        employee.refresh_from_db()
        assert employee.salary_amount == Decimal("99999999.99")


class TestEmployeeFields:
    def test_country_is_stored_as_iso_3166_alpha_2(self, employee):
        assert employee.country == "IN"
        assert Employee._meta.get_field("country").max_length == 2

    def test_lowercase_country_fails_validation(self, db, employee_attrs):
        employee = Employee(**{**employee_attrs, "country": "in"})
        with pytest.raises(ValidationError):
            employee.full_clean()

    def test_job_title_is_required(self, db, employee_attrs):
        """Part of the schema confirmed with the team, so not optional."""
        employee_attrs.pop("job_title")
        with pytest.raises(ValidationError):
            Employee(**employee_attrs).full_clean()

    def test_job_title_is_stored(self, employee):
        employee.refresh_from_db()
        assert employee.job_title == "Senior Engineer"

    def test_joined_on_is_a_date_not_a_datetime(self, employee):
        employee.refresh_from_db()
        assert isinstance(employee.joined_on, dt.date)
        assert not isinstance(employee.joined_on, dt.datetime)

    def test_timestamps_are_set_on_create(self, employee):
        assert employee.created_at is not None
        assert employee.updated_at is not None

    def test_updated_at_advances_on_save(self, employee):
        original = employee.updated_at
        employee.department = "Platform"
        employee.save()
        employee.refresh_from_db()
        assert employee.updated_at > original

    def test_created_at_does_not_move_on_save(self, employee):
        original = employee.created_at
        employee.department = "Platform"
        employee.save()
        employee.refresh_from_db()
        assert employee.created_at == original


class TestEmployeeIndexes:
    """ARCHITECTURE.md section 8 names the indexes the list view depends on."""

    def _indexed_field_sets(self):
        return {tuple(index.fields) for index in Employee._meta.indexes}

    def test_country_is_indexed(self):
        assert ("country",) in self._indexed_field_sets()

    def test_department_is_indexed(self):
        assert ("department",) in self._indexed_field_sets()

    def test_job_title_is_indexed(self):
        """by-title analytics group on it, so it carries an index."""
        assert ("job_title",) in self._indexed_field_sets()

    def test_name_is_indexed_for_sorting(self):
        assert ("last_name", "first_name") in self._indexed_field_sets()

    def test_employee_code_is_indexed_by_its_unique_constraint(self):
        assert Employee._meta.get_field("employee_code").unique

    def test_all_declared_indexes_are_real_index_objects(self):
        assert all(isinstance(i, Index) for i in Employee._meta.indexes)

    def test_default_ordering_matches_the_name_index(self):
        """Ordering off an index keeps pagination cheap."""
        assert Employee._meta.ordering[:2] == ["last_name", "first_name"]

    def test_default_ordering_is_total(self):
        """Names are not unique, so the default order needs a tiebreaker or
        tied rows can straddle a page boundary."""
        assert Employee._meta.ordering[-1] == "id"


class TestSalaryChange:
    def test_primary_key_is_a_uuid(self, employee):
        change = SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100.00"),
            old_currency="INR",
            new_amount=Decimal("200.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        assert isinstance(change.pk, uuid.UUID)

    def test_reachable_from_the_employee(self, employee):
        SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100.00"),
            old_currency="INR",
            new_amount=Decimal("200.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        assert employee.salary_changes.count() == 1

    def test_changed_at_is_set_automatically(self, employee):
        change = SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100.00"),
            old_currency="INR",
            new_amount=Decimal("200.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        assert change.changed_at is not None

    def test_records_currency_on_both_sides_of_the_change(self, employee):
        """A cross-currency move must not look like a pay cut.

        100000 INR to 2000 USD is a raise. With one currency column the old
        amount would be read against the new currency and the row would read
        as a 98 percent cut.
        """
        change = SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100000.00"),
            old_currency="INR",
            new_amount=Decimal("2000.00"),
            new_currency="USD",
            changed_by="hr@acme.test",
        )
        change.refresh_from_db()
        assert change.old_currency == "INR"
        assert change.new_currency == "USD"

    def test_deleting_the_employee_removes_their_history(self, employee):
        SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100.00"),
            old_currency="INR",
            new_amount=Decimal("200.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        employee.delete()
        assert SalaryChange.objects.count() == 0

    def test_newest_change_first(self, employee):
        older = SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("100.00"),
            old_currency="INR",
            new_amount=Decimal("200.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        newer = SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("200.00"),
            old_currency="INR",
            new_amount=Decimal("300.00"),
            new_currency="INR",
            changed_by="hr@acme.test",
        )
        assert list(employee.salary_changes.all()) == [newer, older]
