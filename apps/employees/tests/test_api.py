"""HTTP contract for /api/v1/employees.

Views are thin, so these assert the contract -- status codes, payload shape,
and that the API routes through the service layer rather than around it.
"""

from decimal import Decimal

import pytest
from rest_framework import status

from apps.employees.models import Employee, SalaryChange

LIST_URL = "/api/v1/employees/"


def detail_url(employee):
    return f"{LIST_URL}{employee.pk}/"


@pytest.fixture
def payload():
    return {
        "employee_code": "ACME-9001",
        "first_name": "Marco",
        "last_name": "Bianchi",
        "department": "Finance",
        "job_title": "Financial Analyst",
        "country": "IT",
        "joined_on": "2022-09-15",
        "salary_amount": "60000.00",
        "currency": "EUR",
    }


class TestList:
    def test_returns_200(self, fx_rates, api_client, employee):
        assert api_client.get(LIST_URL).status_code == status.HTTP_200_OK

    def test_is_paginated(self, fx_rates, api_client, employee):
        body = api_client.get(LIST_URL).json()
        assert body["count"] == 1
        assert len(body["results"]) == 1

    def test_exposes_the_normalised_salary(self, fx_rates, api_client, employee):
        row = api_client.get(LIST_URL).json()["results"][0]
        assert row["salary_usd"] == "28800.00"

    def test_money_is_serialised_as_a_string_not_a_float(
        self, fx_rates, api_client, employee
    ):
        """JSON numbers are doubles; sending money as one reintroduces drift."""
        row = api_client.get(LIST_URL).json()["results"][0]
        assert isinstance(row["salary_amount"], str)
        assert isinstance(row["salary_usd"], str)


class TestJobTitle:
    """Confirmed part of the schema (REQUIREMENTS.md section 4)."""

    def test_is_returned_by_the_list_view(self, fx_rates, api_client, employee):
        row = api_client.get(LIST_URL).json()["results"][0]
        assert row["job_title"] == "Senior Engineer"

    def test_is_accepted_on_create(self, fx_rates, api_client, payload):
        response = api_client.post(LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["job_title"] == "Financial Analyst"

    def test_missing_job_title_is_rejected(self, fx_rates, api_client, payload):
        del payload["job_title"]
        response = api_client.post(LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "job_title" in response.json()

    def test_list_can_be_filtered_by_job_title(
        self, fx_rates, api_client, employee, make_employee
    ):
        # Two distinct titles, so the assertion fails if filtering is a no-op.
        make_employee(employee_code="ACME-0002", job_title="Product Manager")
        body = api_client.get(LIST_URL, {"job_title": "Product Manager"}).json()
        assert body["count"] == 1
        assert body["results"][0]["job_title"] == "Product Manager"

    def test_list_can_be_ordered_by_job_title(
        self, fx_rates, api_client, employee, make_employee
    ):
        make_employee(employee_code="ACME-0002", job_title="Analyst")
        body = api_client.get(LIST_URL, {"ordering": "job_title"}).json()
        assert [r["job_title"] for r in body["results"]] == [
            "Analyst",
            "Senior Engineer",
        ]


class TestRetrieve:
    def test_returns_the_employee(self, fx_rates, api_client, employee):
        response = api_client.get(detail_url(employee))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["employee_code"] == "ACME-0001"

    def test_unknown_id_returns_404(self, fx_rates, api_client):
        missing = "00000000-0000-4000-8000-000000000000"
        assert (
            api_client.get(f"{LIST_URL}{missing}/").status_code
            == status.HTTP_404_NOT_FOUND
        )


class TestCreate:
    def test_returns_201(self, fx_rates, api_client, payload):
        assert (
            api_client.post(LIST_URL, payload, format="json").status_code
            == status.HTTP_201_CREATED
        )

    def test_computes_salary_usd(self, fx_rates, api_client, payload):
        # 60000 EUR * 1.08 = 64800.00
        body = api_client.post(LIST_URL, payload, format="json").json()
        assert body["salary_usd"] == "64800.00"

    def test_ignores_a_client_supplied_salary_usd(self, fx_rates, api_client, payload):
        """salary_usd is derived. Letting a client set it would let them lie."""
        response = api_client.post(
            LIST_URL, {**payload, "salary_usd": "999999.00"}, format="json"
        )
        assert response.json()["salary_usd"] == "64800.00"

    def test_persists_the_employee(self, fx_rates, api_client, payload):
        api_client.post(LIST_URL, payload, format="json")
        assert Employee.objects.filter(employee_code="ACME-9001").exists()

    def test_writes_no_audit_row(self, fx_rates, api_client, payload):
        api_client.post(LIST_URL, payload, format="json")
        assert SalaryChange.objects.count() == 0


class TestCreateNormalisesInput:
    """Strictness lives in core.to_usd; forgiveness lives here at the edge."""

    def test_lowercase_currency_is_accepted(self, fx_rates, api_client, payload):
        response = api_client.post(
            LIST_URL, {**payload, "currency": "eur"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_lowercase_currency_is_stored_uppercase(
        self, fx_rates, api_client, payload
    ):
        api_client.post(LIST_URL, {**payload, "currency": "eur"}, format="json")
        assert Employee.objects.get(employee_code="ACME-9001").currency == "EUR"

    def test_mixed_case_currency_is_normalised(self, fx_rates, api_client, payload):
        api_client.post(LIST_URL, {**payload, "currency": "eUr"}, format="json")
        assert Employee.objects.get(employee_code="ACME-9001").currency == "EUR"

    def test_normalised_currency_still_converts(self, fx_rates, api_client, payload):
        body = api_client.post(
            LIST_URL, {**payload, "currency": "eur"}, format="json"
        ).json()
        assert body["salary_usd"] == "64800.00"

    def test_lowercase_country_is_stored_uppercase(self, fx_rates, api_client, payload):
        api_client.post(LIST_URL, {**payload, "country": "it"}, format="json")
        assert Employee.objects.get(employee_code="ACME-9001").country == "IT"

    def test_surrounding_whitespace_is_stripped(self, fx_rates, api_client, payload):
        api_client.post(LIST_URL, {**payload, "currency": " eur "}, format="json")
        assert Employee.objects.get(employee_code="ACME-9001").currency == "EUR"


class TestCreateValidation:
    def test_negative_salary_is_rejected(self, fx_rates, api_client, payload):
        response = api_client.post(
            LIST_URL, {**payload, "salary_amount": "-1.00"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "salary_amount" in response.json()

    def test_unsupported_currency_is_rejected(self, fx_rates, api_client, payload):
        response = api_client.post(
            LIST_URL, {**payload, "currency": "ZAR"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "currency" in response.json()

    def test_nothing_is_persisted_when_validation_fails(
        self, fx_rates, api_client, payload
    ):
        api_client.post(LIST_URL, {**payload, "currency": "ZAR"}, format="json")
        assert Employee.objects.count() == 0

    def test_duplicate_employee_code_is_rejected(
        self, fx_rates, api_client, payload, employee
    ):
        response = api_client.post(
            LIST_URL, {**payload, "employee_code": "ACME-0001"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "employee_code" in response.json()

    def test_missing_required_field_is_rejected(self, fx_rates, api_client, payload):
        del payload["employee_code"]
        response = api_client.post(LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "employee_code" in response.json()

    def test_malformed_date_is_rejected(self, fx_rates, api_client, payload):
        response = api_client.post(
            LIST_URL, {**payload, "joined_on": "15/09/2022"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "joined_on" in response.json()

    def test_invalid_country_is_rejected(self, fx_rates, api_client, payload):
        response = api_client.post(
            LIST_URL, {**payload, "country": "Italy"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "country" in response.json()


class TestUpdate:
    def test_patching_salary_returns_200(self, fx_rates, api_client, employee):
        response = api_client.patch(
            detail_url(employee), {"salary_amount": "3000000.00"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patching_salary_recomputes_salary_usd(
        self, fx_rates, api_client, employee
    ):
        # 3000000 INR * 0.012 = 36000.00
        body = api_client.patch(
            detail_url(employee), {"salary_amount": "3000000.00"}, format="json"
        ).json()
        assert body["salary_usd"] == "36000.00"

    def test_patching_salary_writes_an_audit_row(self, fx_rates, api_client, employee):
        api_client.patch(
            detail_url(employee), {"salary_amount": "3000000.00"}, format="json"
        )
        assert employee.salary_changes.count() == 1

    def test_audit_row_names_the_requesting_user(
        self, fx_rates, api_client, employee, hr_user
    ):
        """The trail records the actual actor, not a placeholder."""
        api_client.patch(
            detail_url(employee), {"salary_amount": "3000000.00"}, format="json"
        )
        assert employee.salary_changes.get().changed_by == hr_user.get_username()

    def test_patching_a_non_salary_field_writes_no_audit_row(
        self, fx_rates, api_client, employee
    ):
        api_client.patch(
            detail_url(employee), {"department": "Platform"}, format="json"
        )
        assert SalaryChange.objects.count() == 0

    def test_put_replaces_the_record(self, fx_rates, api_client, employee, payload):
        response = api_client.put(detail_url(employee), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        employee.refresh_from_db()
        assert employee.department == "Finance"

    def test_patching_currency_writes_an_audit_row(
        self, fx_rates, api_client, employee
    ):
        api_client.patch(detail_url(employee), {"currency": "usd"}, format="json")
        change = employee.salary_changes.get()
        assert change.old_currency == "INR"
        assert change.new_currency == "USD"

    def test_invalid_update_is_rejected(self, fx_rates, api_client, employee):
        response = api_client.patch(
            detail_url(employee), {"salary_amount": "-5.00"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDelete:
    def test_returns_204(self, fx_rates, api_client, employee):
        assert (
            api_client.delete(detail_url(employee)).status_code
            == status.HTTP_204_NO_CONTENT
        )

    def test_removes_the_employee(self, fx_rates, api_client, employee):
        api_client.delete(detail_url(employee))
        assert Employee.objects.count() == 0

    def test_removes_their_salary_history(self, fx_rates, api_client, employee):
        api_client.patch(
            detail_url(employee), {"salary_amount": "3000000.00"}, format="json"
        )
        api_client.delete(detail_url(employee))
        assert SalaryChange.objects.count() == 0


class TestAuthentication:
    """Full auth is Phase 7; this pins the default posture already in place."""

    @pytest.mark.parametrize(
        "method", ["get", "post", "patch", "put", "delete"]
    )
    def test_anonymous_access_is_denied(
        self, fx_rates, anonymous_client, employee, method
    ):
        url = LIST_URL if method in {"get", "post"} else detail_url(employee)
        response = getattr(anonymous_client, method)(url)
        assert response.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }


class TestQueryEfficiency:
    def test_list_does_not_scale_queries_with_row_count(
        self, fx_rates, api_client, make_employee, django_assert_num_queries
    ):
        """Guards against an N+1 creeping in as the serializer grows."""
        for i in range(2, 12):
            make_employee(employee_code=f"ACME-{i:04d}")

        with django_assert_num_queries(2):  # count + page
            api_client.get(LIST_URL)
