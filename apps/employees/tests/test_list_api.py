"""Server-side list behaviour on GET /api/v1/employees.

Pagination, filtering, search and ordering all happen in the database. The
browser never receives 10,000 rows (ARCHITECTURE.md section 8).
"""

import uuid
import warnings
from decimal import Decimal

import pytest
from django.core.paginator import UnorderedObjectListWarning
from rest_framework import status

LIST_URL = "/api/v1/employees/"


@pytest.fixture
def dataset(fx_rates, make_employee):
    """Four employees across four countries and currencies.

    salary_usd is hand-computed from the seeded FX rates.
    """
    return [
        make_employee(
            employee_code="ACME-1001",
            first_name="Asha",
            last_name="Rao",
            department="Engineering",
            job_title="Senior Engineer",
            country="IN",
            currency="INR",
            salary_amount=Decimal("2400000.00"),  # * 0.012
            salary_usd=Decimal("28800.00"),
        ),
        make_employee(
            employee_code="ACME-1002",
            first_name="Marco",
            last_name="Bianchi",
            department="Finance",
            job_title="Analyst",
            country="IT",
            currency="EUR",
            salary_amount=Decimal("60000.00"),  # * 1.08
            salary_usd=Decimal("64800.00"),
        ),
        make_employee(
            employee_code="ACME-1003",
            first_name="Yuki",
            last_name="Tanaka",
            department="Engineering",
            job_title="Staff Engineer",
            country="JP",
            currency="JPY",
            salary_amount=Decimal("9000000.00"),  # * 0.0064
            salary_usd=Decimal("57600.00"),
        ),
        make_employee(
            employee_code="ACME-1004",
            first_name="Grace",
            last_name="Adeyemi",
            department="People",
            job_title="Recruiter",
            country="GB",
            currency="GBP",
            salary_amount=Decimal("52000.00"),  # * 1.27
            salary_usd=Decimal("66040.00"),
        ),
    ]


def codes(response):
    return [row["employee_code"] for row in response.json()["results"]]


class TestPaginationContract:
    """DRF's default page-number shape.

    Phase 8's Ant Design Table consumes it directly, so it stays standard
    rather than custom.
    """

    def test_response_has_the_standard_keys(self, dataset, api_client):
        assert set(api_client.get(LIST_URL).json()) == {
            "count",
            "next",
            "previous",
            "results",
        }

    def test_page_size_defaults_to_25(self, fx_rates, api_client, make_employee):
        for i in range(30):
            make_employee(employee_code=f"BULK-{i:04d}")
        body = api_client.get(LIST_URL).json()
        assert body["count"] == 30
        assert len(body["results"]) == 25

    def test_second_page_holds_the_remainder(
        self, fx_rates, api_client, make_employee
    ):
        for i in range(30):
            make_employee(employee_code=f"BULK-{i:04d}")
        body = api_client.get(LIST_URL, {"page": 2}).json()
        assert len(body["results"]) == 5
        assert body["previous"] is not None
        assert body["next"] is None

    def test_no_next_link_on_a_single_page(self, dataset, api_client):
        assert api_client.get(LIST_URL).json()["next"] is None

    def test_out_of_range_page_returns_404(self, dataset, api_client):
        response = api_client.get(LIST_URL, {"page": 99})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_result_set_is_not_an_error(self, dataset, api_client):
        body = api_client.get(LIST_URL, {"country": "ZZ"}).json()
        assert body["count"] == 0
        assert body["results"] == []


class TestFiltering:
    def test_by_country(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"country": "IN"})) == ["ACME-1001"]

    def test_by_department(self, dataset, api_client):
        response = api_client.get(LIST_URL, {"department": "Engineering"})
        assert sorted(codes(response)) == ["ACME-1001", "ACME-1003"]

    def test_by_job_title(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"job_title": "Recruiter"})) == [
            "ACME-1004"
        ]

    def test_by_currency(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"currency": "JPY"})) == ["ACME-1003"]

    def test_combined_filters_narrow(self, dataset, api_client):
        response = api_client.get(
            LIST_URL, {"department": "Engineering", "country": "JP"}
        )
        assert codes(response) == ["ACME-1003"]

    def test_combined_filters_can_exclude_everything(self, dataset, api_client):
        response = api_client.get(
            LIST_URL, {"department": "Engineering", "country": "GB"}
        )
        assert response.json()["count"] == 0

    def test_unknown_filter_value_returns_nothing_not_an_error(
        self, dataset, api_client
    ):
        response = api_client.get(LIST_URL, {"department": "Nonexistent"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 0


class TestSalaryRangeFiltersOnUsd:
    """Salary range filters compare salary_usd, never salary_amount.

    This is the multi-currency design earning its keep. Filtering on the local
    amount would compare an INR figure against a GBP one and return results
    that mean nothing: 1,000,000 INR and 1,000,000 GBP are not remotely
    comparable pay.
    """

    @pytest.fixture
    def same_local_amount(self, fx_rates, make_employee):
        """Three employees paid the same number, in wildly different money."""
        amount = Decimal("1000000.00")
        make_employee(
            employee_code="MC-INR",
            currency="INR",
            salary_amount=amount,
            salary_usd=Decimal("12000.00"),  # 1000000 * 0.012
        )
        make_employee(
            employee_code="MC-JPY",
            currency="JPY",
            salary_amount=amount,
            salary_usd=Decimal("6400.00"),  # 1000000 * 0.0064
        )
        make_employee(
            employee_code="MC-GBP",
            currency="GBP",
            salary_amount=amount,
            salary_usd=Decimal("1270000.00"),  # 1000000 * 1.27
        )

    def test_range_selects_by_usd_value_not_local_number(
        self, same_local_amount, api_client
    ):
        """All three share salary_amount.

        A filter on the local column would return all three or none. Only the
        USD figures separate them.
        """
        response = api_client.get(
            LIST_URL, {"salary_usd_min": "10000", "salary_usd_max": "100000"}
        )
        assert codes(response) == ["MC-INR"]

    def test_min_excludes_the_weakest_currency(self, same_local_amount, api_client):
        response = api_client.get(LIST_URL, {"salary_usd_min": "10000"})
        assert sorted(codes(response)) == ["MC-GBP", "MC-INR"]

    def test_max_excludes_the_strongest_currency(self, same_local_amount, api_client):
        response = api_client.get(LIST_URL, {"salary_usd_max": "100000"})
        assert sorted(codes(response)) == ["MC-INR", "MC-JPY"]

    def test_min_is_inclusive(self, same_local_amount, api_client):
        response = api_client.get(LIST_URL, {"salary_usd_min": "12000"})
        assert "MC-INR" in codes(response)

    def test_max_is_inclusive(self, same_local_amount, api_client):
        response = api_client.get(LIST_URL, {"salary_usd_max": "12000"})
        assert "MC-INR" in codes(response)

    def test_range_across_the_mixed_dataset(self, dataset, api_client):
        # 28800, 57600, 64800, 66040 -> only the middle two fall in range.
        response = api_client.get(
            LIST_URL, {"salary_usd_min": "57000", "salary_usd_max": "65000"}
        )
        assert sorted(codes(response)) == ["ACME-1002", "ACME-1003"]

    def test_non_numeric_bound_is_rejected(self, dataset, api_client):
        response = api_client.get(LIST_URL, {"salary_usd_min": "lots"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestSearch:
    def test_by_first_name(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"search": "Yuki"})) == ["ACME-1003"]

    def test_by_last_name(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"search": "Adeyemi"})) == ["ACME-1004"]

    def test_by_employee_code(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"search": "ACME-1002"})) == [
            "ACME-1002"
        ]

    def test_is_case_insensitive(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"search": "yuki"})) == ["ACME-1003"]

    def test_matches_a_partial_name(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"search": "Tana"})) == ["ACME-1003"]

    def test_no_match_returns_empty(self, dataset, api_client):
        assert api_client.get(LIST_URL, {"search": "Nobody"}).json()["count"] == 0

    def test_does_not_search_department(self, dataset, api_client):
        """Search covers names and code. Department has its own filter."""
        assert api_client.get(LIST_URL, {"search": "Finance"}).json()["count"] == 0


class TestOrdering:
    def test_by_last_name(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"ordering": "last_name"})) == [
            "ACME-1004",  # Adeyemi
            "ACME-1002",  # Bianchi
            "ACME-1001",  # Rao
            "ACME-1003",  # Tanaka
        ]

    def test_by_salary_usd_ascending(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"ordering": "salary_usd"})) == [
            "ACME-1001",  # 28800
            "ACME-1003",  # 57600
            "ACME-1002",  # 64800
            "ACME-1004",  # 66040
        ]

    def test_by_salary_usd_descending(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL, {"ordering": "-salary_usd"})) == [
            "ACME-1004",
            "ACME-1002",
            "ACME-1003",
            "ACME-1001",
        ]

    def test_by_joined_on(self, dataset, api_client):
        response = api_client.get(LIST_URL, {"ordering": "joined_on"})
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_ordering_field_is_ignored(self, dataset, api_client):
        """DRF drops unrecognised fields rather than erroring.

        That keeps a stale frontend query from breaking the page.
        """
        response = api_client.get(LIST_URL, {"ordering": "salary_in_gold"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 4

    def test_default_ordering_is_by_name(self, dataset, api_client):
        assert codes(api_client.get(LIST_URL))[0] == "ACME-1004"  # Adeyemi


class TestDeterministicOrdering:
    """Ordering on a non-unique column must still be total.

    Without a tiebreaker, rows that compare equal come back in whatever order
    the database happens to produce. Across a paginated read that means a row
    can appear on two pages, or on none: the classic pagination bug, and
    invisible until a page boundary lands inside a tie.
    """

    @pytest.fixture
    def tied_salaries(self, fx_rates, make_employee):
        """Five employees on identical pay, inserted in reverse id order.

        The ids are fixed rather than random, so "sorted by id" is provably
        different from "insertion order". Without an id tiebreaker SQLite
        returns insertion order and these tests fail.
        """
        ids = [uuid.UUID(f"00000000-0000-4000-8000-{i:012d}") for i in range(1, 6)]
        for position, identifier in enumerate(reversed(ids)):
            make_employee(
                id=identifier,
                employee_code=f"TIE-{position}",
                last_name="Same",
                first_name="Same",
                salary_amount=Decimal("100000.00"),
                salary_usd=Decimal("1200.00"),
            )
        return ids

    def test_ties_are_broken_by_id(self, tied_salaries, api_client):
        response = api_client.get(LIST_URL, {"ordering": "salary_usd"})
        returned = [uuid.UUID(row["id"]) for row in response.json()["results"]]
        assert returned == tied_salaries

    def test_descending_order_also_breaks_ties_by_id(self, tied_salaries, api_client):
        response = api_client.get(LIST_URL, {"ordering": "-salary_usd"})
        returned = [uuid.UUID(row["id"]) for row in response.json()["results"]]
        assert returned == tied_salaries

    def test_default_ordering_breaks_ties_by_id(self, tied_salaries, api_client):
        """Identical names, so Meta.ordering alone cannot separate them."""
        response = api_client.get(LIST_URL)
        returned = [uuid.UUID(row["id"]) for row in response.json()["results"]]
        assert returned == tied_salaries

    def test_repeated_requests_return_the_same_order(self, tied_salaries, api_client):
        first = codes(api_client.get(LIST_URL, {"ordering": "salary_usd"}))
        second = codes(api_client.get(LIST_URL, {"ordering": "salary_usd"}))
        assert first == second

    def test_pages_do_not_overlap_across_a_tie(
        self, fx_rates, api_client, make_employee
    ):
        """30 employees on identical pay, so every page boundary is a tie."""
        for i in range(30):
            make_employee(
                employee_code=f"TIE-{i:04d}",
                last_name="Same",
                first_name="Same",
                salary_amount=Decimal("100000.00"),
                salary_usd=Decimal("1200.00"),
            )
        params = {"ordering": "salary_usd"}
        page_one = codes(api_client.get(LIST_URL, params))
        page_two = codes(api_client.get(LIST_URL, {**params, "page": 2}))

        assert set(page_one) & set(page_two) == set()
        assert len(set(page_one) | set(page_two)) == 30

    def test_no_unordered_pagination_warning(self, dataset, api_client):
        """Django warns when paginating an unordered queryset.

        Treat it as an error so an unordered path cannot slip in unnoticed.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnorderedObjectListWarning)
            response = api_client.get(LIST_URL)
        assert response.status_code == status.HTTP_200_OK


class TestFilterSearchAndOrderTogether:
    def test_all_three_compose(self, dataset, api_client, make_employee):
        make_employee(
            employee_code="ACME-1005",
            first_name="Ravi",
            last_name="Rao",
            department="Engineering",
            job_title="Senior Engineer",
            country="IN",
            currency="INR",
            salary_amount=Decimal("3600000.00"),
            salary_usd=Decimal("43200.00"),
        )
        response = api_client.get(
            LIST_URL,
            {
                "department": "Engineering",
                "search": "Rao",
                "ordering": "-salary_usd",
            },
        )
        assert codes(response) == ["ACME-1005", "ACME-1001"]

    def test_filter_and_range_compose(self, dataset, api_client):
        response = api_client.get(
            LIST_URL, {"department": "Engineering", "salary_usd_min": "50000"}
        )
        assert codes(response) == ["ACME-1003"]

    def test_pagination_survives_filtering(self, fx_rates, api_client, make_employee):
        for i in range(30):
            make_employee(employee_code=f"ENG-{i:04d}", department="Engineering")
        for i in range(5):
            make_employee(employee_code=f"FIN-{i:04d}", department="Finance")
        body = api_client.get(LIST_URL, {"department": "Engineering"}).json()
        assert body["count"] == 30
        assert len(body["results"]) == 25


class TestQueryContract:
    """Pin the query count, not just the absence of an N+1.

    Employee has no forward relations yet, so an N+1 cannot occur here today
    and this assertion would be cargo-culted if that were its only purpose.
    The point is forward-looking: it fixes the contract at two queries -- one
    COUNT for pagination, one SELECT for the page -- so that when salary
    history, a department FK or any other relation reaches this serializer,
    the extra per-row query trips this test immediately rather than surfacing
    as a slow page at 10,000 rows.
    """

    def test_plain_list_costs_two_queries(
        self, fx_rates, api_client, make_employee, django_assert_num_queries
    ):
        for i in range(30):
            make_employee(employee_code=f"BULK-{i:04d}")
        with django_assert_num_queries(2):
            api_client.get(LIST_URL)

    def test_query_count_is_independent_of_row_count(
        self, fx_rates, api_client, make_employee, django_assert_num_queries
    ):
        for i in range(60):
            make_employee(employee_code=f"BULK-{i:04d}")
        with django_assert_num_queries(2):
            api_client.get(LIST_URL)

    def test_filtering_searching_and_ordering_add_no_queries(
        self, dataset, api_client, django_assert_num_queries
    ):
        with django_assert_num_queries(2):
            api_client.get(
                LIST_URL,
                {
                    "department": "Engineering",
                    "salary_usd_min": "10000",
                    "search": "Rao",
                    "ordering": "-salary_usd",
                },
            )
