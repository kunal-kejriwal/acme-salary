"""GET /api/v1/employees/{id}/salary-history.

The audit trail (F3), read back per employee. This is what the detail page's
History tab renders, and what makes a pay change visible immediately after it
is made.
"""

from decimal import Decimal

import pytest
from rest_framework import status

from apps.employees.services import update_employee


def history_url(employee):
    return f"/api/v1/employees/{employee.pk}/salary-history/"


@pytest.fixture
def raised(fx_rates, employee):
    update_employee(
        employee, salary_amount=Decimal("3000000.00"), changed_by="hr@acme.test"
    )
    return employee


class TestSalaryHistory:
    def test_returns_200(self, fx_rates, api_client, employee):
        assert api_client.get(history_url(employee)).status_code == (
            status.HTTP_200_OK
        )

    def test_is_empty_before_any_change(self, fx_rates, api_client, employee):
        """A newly hired employee has a salary, not a change.

        The History tab renders this as an intentional empty state.
        """
        assert api_client.get(history_url(employee)).json()["results"] == []

    def test_a_raise_appears(self, fx_rates, api_client, raised):
        body = api_client.get(history_url(raised)).json()
        assert body["count"] == 1

    def test_records_both_sides_of_the_change(self, fx_rates, api_client, raised):
        row = api_client.get(history_url(raised)).json()["results"][0]
        assert row["old_amount"] == "2400000.00"
        assert row["new_amount"] == "3000000.00"
        assert row["old_currency"] == "INR"
        assert row["new_currency"] == "INR"

    def test_names_the_actor_and_the_moment(self, fx_rates, api_client, raised):
        row = api_client.get(history_url(raised)).json()["results"][0]
        assert row["changed_by"] == "hr@acme.test"
        assert row["changed_at"]

    def test_money_is_a_string_not_a_json_number(self, fx_rates, api_client, raised):
        row = api_client.get(history_url(raised)).json()["results"][0]
        assert isinstance(row["old_amount"], str)
        assert isinstance(row["new_amount"], str)

    def test_newest_change_first(self, fx_rates, api_client, employee):
        update_employee(
            employee, salary_amount=Decimal("3000000.00"), changed_by="hr@acme.test"
        )
        update_employee(
            employee, salary_amount=Decimal("3600000.00"), changed_by="hr@acme.test"
        )
        rows = api_client.get(history_url(employee)).json()["results"]
        assert [row["new_amount"] for row in rows] == [
            "3600000.00",
            "3000000.00",
        ]

    def test_only_this_employees_history(
        self, fx_rates, api_client, employee, make_employee
    ):
        other = make_employee(employee_code="ACME-0002")
        update_employee(
            other, salary_amount=Decimal("9000000.00"), changed_by="hr@acme.test"
        )
        update_employee(
            employee, salary_amount=Decimal("3000000.00"), changed_by="hr@acme.test"
        )
        rows = api_client.get(history_url(employee)).json()["results"]
        assert len(rows) == 1
        assert rows[0]["new_amount"] == "3000000.00"

    def test_unknown_employee_is_404(self, fx_rates, api_client):
        missing = "00000000-0000-4000-8000-000000000000"
        assert api_client.get(
            f"/api/v1/employees/{missing}/salary-history/"
        ).status_code == status.HTTP_404_NOT_FOUND

    def test_is_paginated_like_the_rest_of_the_api(
        self, fx_rates, api_client, raised
    ):
        body = api_client.get(history_url(raised)).json()
        assert set(body) == {"count", "next", "previous", "results"}

    def test_is_read_only(self, fx_rates, api_client, employee):
        response = api_client.post(history_url(employee), {}, format="json")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_costs_three_queries(
        self, fx_rates, api_client, raised, django_assert_num_queries
    ):
        """Employee lookup, COUNT, page.

        The employee lookup is deliberate: filtering SalaryChange by id alone
        would save it, but then an unknown employee returns an empty list
        instead of a 404 -- indistinguishable from someone who has simply
        never had a raise. One query buys a correct answer.
        """
        with django_assert_num_queries(3):
            api_client.get(history_url(raised))
