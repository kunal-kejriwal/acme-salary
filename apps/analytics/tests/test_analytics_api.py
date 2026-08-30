"""Analytics endpoints, all figures in USD.

Every expected value here is hand-computed from the fixture below, never read
back out of the code. The fixture is deliberately skewed so the median and the
mean differ — an analytics suite where they coincide cannot tell you which one
the implementation actually computed.
"""

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework import status

from apps.employees.services import create_employee

SUMMARY_URL = "/api/v1/analytics/summary/"
BY_COUNTRY_URL = "/api/v1/analytics/by-country/"
BY_DEPARTMENT_URL = "/api/v1/analytics/by-department/"
BY_TITLE_URL = "/api/v1/analytics/by-title/"

# (code, country, currency, local amount, department, title) -> USD
#   USD  10000 * 1.00  =  10000
#   USD  20000 * 1.00  =  20000
#   USD  30000 * 1.00  =  30000
#   USD 400000 * 1.00  = 400000
#   INR 2500000 * 0.012 = 30000
#   JPY 5000000 * 0.0064 = 32000
#   GBP 20000 * 1.27   =  25400
#   EUR 25000 * 1.08   =  27000
PEOPLE = [
    ("A-1", "US", "USD", "10000.00", "Engineering", "Engineer"),
    ("A-2", "US", "USD", "20000.00", "Engineering", "Engineer"),
    ("A-3", "US", "USD", "30000.00", "Finance", "Analyst"),
    ("A-4", "US", "USD", "400000.00", "Finance", "Director"),
    ("A-5", "IN", "INR", "2500000.00", "Engineering", "Senior Engineer"),
    ("A-6", "JP", "JPY", "5000000.00", "Engineering", "Senior Engineer"),
    ("A-7", "GB", "GBP", "20000.00", "People", "Recruiter"),
    ("A-8", "DE", "EUR", "25000.00", "People", "Manager"),
]

# Sorted USD: 10000, 20000, 25400, 27000, 30000, 30000, 32000, 400000
#   n = 8, total = 574400, mean = 71800, median = (27000 + 30000) / 2 = 28500
TOTAL = Decimal("574400.00")
MEAN = Decimal("71800.00")
MEDIAN = Decimal("28500.00")


@pytest.fixture
def org(fx_rates):
    for code, country, currency, amount, department, title in PEOPLE:
        create_employee(
            employee_code=code,
            first_name="Test",
            last_name=code,
            department=department,
            job_title=title,
            country=country,
            joined_on=dt.date(2022, 1, 1),
            salary_amount=Decimal(amount),
            currency=currency,
        )


def groups(response):
    return {row["group"]: row for row in response.json()}


class TestSummary:
    def test_returns_200(self, org, api_client):
        assert api_client.get(SUMMARY_URL).status_code == status.HTTP_200_OK

    def test_headcount(self, org, api_client):
        assert api_client.get(SUMMARY_URL).json()["headcount"] == 8

    def test_total_annual_cost(self, org, api_client):
        assert api_client.get(SUMMARY_URL).json()["total_usd"] == str(TOTAL)

    def test_average(self, org, api_client):
        assert api_client.get(SUMMARY_URL).json()["average_usd"] == str(MEAN)

    def test_median(self, org, api_client):
        assert api_client.get(SUMMARY_URL).json()["median_usd"] == str(MEDIAN)

    def test_median_is_not_the_mean(self, org, api_client):
        """The fixture is skewed on purpose.

        If these matched, no assertion in this file could tell a median
        implementation from a mean one.
        """
        body = api_client.get(SUMMARY_URL).json()
        assert body["median_usd"] != body["average_usd"]

    def test_money_is_a_string_not_a_json_number(self, org, api_client):
        """JSON numbers are doubles. Money must not travel as one."""
        body = api_client.get(SUMMARY_URL).json()
        for key in ("total_usd", "average_usd", "median_usd"):
            assert isinstance(body[key], str), key


class TestSummaryOnAnEmptyDatabase:
    """Zeros, not nulls, and certainly not a 500."""

    def test_returns_200(self, fx_rates, api_client):
        assert api_client.get(SUMMARY_URL).status_code == status.HTTP_200_OK

    def test_headcount_is_zero(self, fx_rates, api_client):
        assert api_client.get(SUMMARY_URL).json()["headcount"] == 0

    def test_money_fields_are_zero(self, fx_rates, api_client):
        body = api_client.get(SUMMARY_URL).json()
        assert body["total_usd"] == "0.00"
        assert body["average_usd"] == "0.00"
        assert body["median_usd"] == "0.00"


class TestByCountry:
    # US: 10000, 20000, 30000, 400000 -> n=4, mean 115000, median 25000
    def test_group_count(self, org, api_client):
        """Five countries, not eight rows.

        Employee.Meta.ordering would leak into the GROUP BY if the queryset
        did not order explicitly, silently grouping by (country, name) and
        returning one row per employee.
        """
        assert len(api_client.get(BY_COUNTRY_URL).json()) == 5

    def test_headcounts(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["US"]["headcount"] == 4
        assert rows["IN"]["headcount"] == 1

    def test_average(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["US"]["average_usd"] == "115000.00"

    def test_median(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["US"]["median_usd"] == "25000.00"

    def test_group_median_differs_from_group_mean(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["US"]["median_usd"] != rows["US"]["average_usd"]

    def test_min_and_max(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["US"]["min_usd"] == "10000.00"
        assert rows["US"]["max_usd"] == "400000.00"

    def test_single_member_group_is_its_own_median(self, org, api_client):
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["IN"]["median_usd"] == "30000.00"
        assert rows["IN"]["average_usd"] == "30000.00"

    def test_converted_from_local_currency(self, org, api_client):
        """JPY 5,000,000 at 0.0064 is 32,000 USD."""
        rows = groups(api_client.get(BY_COUNTRY_URL))
        assert rows["JP"]["average_usd"] == "32000.00"

    def test_ordered_by_headcount_descending(self, org, api_client):
        order = [row["group"] for row in api_client.get(BY_COUNTRY_URL).json()]
        assert order[0] == "US"

    def test_ties_are_broken_by_group_name(self, org, api_client):
        """Four countries share a headcount of 1.

        Without a tiebreaker their order is whatever the database returns, and
        the dashboard's bars would reshuffle between reloads.
        """
        order = [row["group"] for row in api_client.get(BY_COUNTRY_URL).json()]
        assert order == ["US", "DE", "GB", "IN", "JP"]

    def test_empty_database_returns_an_empty_list(self, fx_rates, api_client):
        response = api_client.get(BY_COUNTRY_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestByDepartment:
    # Engineering: 10000, 20000, 30000, 32000 -> mean 23000, median 25000
    def test_group_count(self, org, api_client):
        assert len(api_client.get(BY_DEPARTMENT_URL).json()) == 3

    def test_headcount(self, org, api_client):
        rows = groups(api_client.get(BY_DEPARTMENT_URL))
        assert rows["Engineering"]["headcount"] == 4

    def test_average(self, org, api_client):
        rows = groups(api_client.get(BY_DEPARTMENT_URL))
        assert rows["Engineering"]["average_usd"] == "23000.00"

    def test_median_exceeds_the_mean_here(self, org, api_client):
        """Skew runs the other way in this group, which the fixture chose
        deliberately: a median that is always below the mean could be a
        coincidence of one distribution."""
        rows = groups(api_client.get(BY_DEPARTMENT_URL))
        assert rows["Engineering"]["median_usd"] == "25000.00"
        assert Decimal(rows["Engineering"]["median_usd"]) > Decimal(
            rows["Engineering"]["average_usd"]
        )

    def test_two_member_group_median_is_the_midpoint(self, org, api_client):
        # People: 25400 and 27000 -> 26200
        rows = groups(api_client.get(BY_DEPARTMENT_URL))
        assert rows["People"]["median_usd"] == "26200.00"

    def test_ordered_by_headcount_then_name(self, org, api_client):
        order = [row["group"] for row in api_client.get(BY_DEPARTMENT_URL).json()]
        assert order == ["Engineering", "Finance", "People"]


class TestByTitle:
    def test_group_count(self, org, api_client):
        assert len(api_client.get(BY_TITLE_URL).json()) == 6

    def test_median_of_a_pair(self, org, api_client):
        # Engineer: 10000 and 20000 -> 15000
        rows = groups(api_client.get(BY_TITLE_URL))
        assert rows["Engineer"]["median_usd"] == "15000.00"

    def test_seniority_shows_in_the_numbers(self, org, api_client):
        rows = groups(api_client.get(BY_TITLE_URL))
        assert Decimal(rows["Senior Engineer"]["median_usd"]) > Decimal(
            rows["Engineer"]["median_usd"]
        )

    def test_ordered_by_headcount_then_name(self, org, api_client):
        order = [row["group"] for row in api_client.get(BY_TITLE_URL).json()]
        assert order[:2] == ["Engineer", "Senior Engineer"]


class TestQueryContract:
    """Two queries per endpoint, whatever the group count.

    One GROUP BY aggregate, plus one window query that returns the middle one
    or two rows per group. Neither scales with the number of groups, which is
    the property that matters: a per-group median would be 200 queries on the
    by-title endpoint at full seed size.
    """

    @pytest.mark.parametrize(
        "url", [SUMMARY_URL, BY_COUNTRY_URL, BY_DEPARTMENT_URL, BY_TITLE_URL]
    )
    def test_costs_two_queries(
        self, org, api_client, django_assert_num_queries, url
    ):
        with django_assert_num_queries(2):
            api_client.get(url)

    def test_query_count_is_independent_of_group_count(
        self, org, api_client, django_assert_num_queries
    ):
        """by-title has six groups here against by-country's five."""
        with django_assert_num_queries(2):
            api_client.get(BY_TITLE_URL)


class TestAuthentication:
    @pytest.mark.parametrize(
        "url", [SUMMARY_URL, BY_COUNTRY_URL, BY_DEPARTMENT_URL, BY_TITLE_URL]
    )
    def test_anonymous_access_is_refused(self, org, anonymous_client, url):
        assert anonymous_client.get(url).status_code == status.HTTP_403_FORBIDDEN


class TestReadOnly:
    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_writes_are_not_allowed(self, org, api_client, method):
        response = getattr(api_client, method)(SUMMARY_URL)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
