"""The seed command.

This is the confirmed way the 10,000 records are populated (REQUIREMENTS.md
section 3), so it carries the load CSV import would otherwise have carried.
"""

import statistics
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.constants import Currency
from apps.core.models import FxRate
from apps.core.seeding import SeedError, seed_employees
from apps.core.services import rate_map, to_usd
from apps.employees.models import Employee, SalaryChange


def business_rows():
    """Every field that the seed is supposed to determine."""
    return list(
        Employee.objects.order_by("employee_code").values_list(
            "id",
            "employee_code",
            "first_name",
            "last_name",
            "department",
            "job_title",
            "country",
            "joined_on",
            "salary_amount",
            "currency",
            "salary_usd",
        )
    )


class TestRowCount:
    def test_creates_exactly_the_requested_number(self, db):
        seed_employees(50)
        assert Employee.objects.count() == 50

    def test_employee_codes_are_unique(self, db):
        seed_employees(200)
        assert Employee.objects.values("employee_code").distinct().count() == 200

    def test_zero_is_allowed(self, db):
        seed_employees(0)
        assert Employee.objects.count() == 0

    def test_negative_count_is_rejected(self, db):
        with pytest.raises(SeedError):
            seed_employees(-1)


class TestDeterminism:
    """Determinism is asserted as a property, not as a stored checksum.

    Hardcoding a hash of the first N rows would fail on any Faker upgrade --
    punishing a routine dependency bump rather than catching a real
    regression, and tempting whoever hits it to paste in the new hash without
    looking. Running the seed twice and comparing asserts the thing that
    actually matters: same seed, same data, whatever Faker's internals do.
    """

    def test_two_runs_produce_identical_rows(self, db):
        seed_employees(100)
        first = business_rows()

        seed_employees(100, flush=True)
        second = business_rows()

        assert first == second

    def test_identity_includes_the_primary_keys(self, db):
        """UUIDs are drawn from the seeded RNG, not uuid4.

        A reproducible dataset that renumbers itself on every run is only
        half reproducible.
        """
        seed_employees(50)
        first = [row[0] for row in business_rows()]

        seed_employees(50, flush=True)
        assert [row[0] for row in business_rows()] == first

    def test_a_different_seed_produces_different_data(self, db):
        """Otherwise the previous tests would pass on a constant generator."""
        seed_employees(100, seed=42)
        first = business_rows()

        seed_employees(100, seed=43, flush=True)
        assert business_rows() != first

    def test_salaries_differ_between_seeds(self, db):
        seed_employees(100, seed=42)
        first = sorted(Employee.objects.values_list("salary_amount", flat=True))

        seed_employees(100, seed=43, flush=True)
        second = sorted(Employee.objects.values_list("salary_amount", flat=True))
        assert first != second


class TestFxRatesArePresent:
    def test_seeding_a_virgin_database_succeeds(self, db):
        """No fx_rates fixture loaded by the test.

        Without the seed loading rates first, row one hits MissingRateError --
        the Phase 1 error taxonomy doing its job, and a bad first-run
        experience.
        """
        assert not FxRate.objects.exists()
        seed_employees(25)
        assert Employee.objects.count() == 25

    def test_rates_are_loaded_as_a_side_effect(self, db):
        seed_employees(10)
        assert set(FxRate.objects.values_list("currency", flat=True)) == set(
            Currency.values
        )

    def test_running_twice_does_not_duplicate_rates(self, db):
        """The fixture has explicit pks, so loading it again updates in place."""
        seed_employees(10)
        seed_employees(10, flush=True)
        assert FxRate.objects.count() == len(Currency.values)

    def test_existing_rates_are_not_disturbed(self, fx_rates):
        seed_employees(10)
        assert FxRate.objects.get(currency="INR").usd_per_unit == Decimal(
            "0.01200000"
        )


class TestSalaryNormalisation:
    def test_every_row_carries_a_usd_figure(self, db):
        seed_employees(100)
        assert not Employee.objects.filter(salary_usd__isnull=True).exists()

    def test_usd_matches_the_local_amount_and_rate(self, db):
        seed_employees(100)
        rates = rate_map()
        for employee in Employee.objects.all():
            assert employee.salary_usd == to_usd(
                employee.salary_amount, employee.currency, rates=rates
            )

    def test_no_salary_is_negative(self, db):
        seed_employees(200)
        assert not Employee.objects.filter(salary_amount__lt=0).exists()

    def test_money_is_stored_as_decimal(self, db):
        seed_employees(10)
        employee = Employee.objects.first()
        assert isinstance(employee.salary_amount, Decimal)
        assert isinstance(employee.salary_usd, Decimal)


@pytest.fixture(scope="class")
def realistic_org(django_db_setup, django_db_blocker):
    """One seeded org shared by a whole class.

    Class-scoped so the realism assertions get a sample large enough to be
    meaningful without re-seeding per test. Torn down at the end of the
    class, so no other test sees these rows.
    """
    with django_db_blocker.unblock():
        Employee.objects.all().delete()
        seed_employees(2500, flush=True)
        yield
        Employee.objects.all().delete()


class TestSalariesAreRealisticInLocalCurrency:
    """A single numeric range for every country produces nonsense.

    80,000 is a fine annual salary in USD, an insultingly low one in INR
    (about 960 USD) and an impossible one in JPY (about 510 USD). Getting
    this wrong makes the dashboard look fake and renders the USD
    normalisation pointless, since every figure would already be comparable.
    """

    def medians_by_currency(self):
        medians = {}
        for currency in Currency.values:
            amounts = list(
                Employee.objects.filter(currency=currency).values_list(
                    "salary_amount", flat=True
                )
            )
            if amounts:
                medians[currency] = statistics.median(amounts)
        return medians

    def test_weak_currencies_carry_much_larger_numbers(self, realistic_org):
        """The property that matters, independent of any exact band."""
        medians = self.medians_by_currency()
        assert medians["INR"] > medians["USD"] * 10
        assert medians["JPY"] > medians["USD"] * 10

    def test_inr_salaries_are_in_lakhs(self, realistic_org):
        assert all(
            amount >= Decimal("100000")
            for amount in Employee.objects.filter(currency="INR").values_list(
                "salary_amount", flat=True
            )
        )

    def test_jpy_salaries_are_in_millions(self, realistic_org):
        assert all(
            amount >= Decimal("1000000")
            for amount in Employee.objects.filter(currency="JPY").values_list(
                "salary_amount", flat=True
            )
        )

    def test_usd_salaries_are_in_tens_of_thousands(self, realistic_org):
        amounts = list(
            Employee.objects.filter(currency="USD").values_list(
                "salary_amount", flat=True
            )
        )
        assert all(Decimal("20000") <= a <= Decimal("1000000") for a in amounts)

    def test_normalised_salaries_land_in_a_plausible_global_band(self, realistic_org):
        """After conversion every salary should look like a real wage."""
        amounts = list(Employee.objects.values_list("salary_usd", flat=True))
        assert all(Decimal("5000") <= a <= Decimal("600000") for a in amounts)

    def test_every_currency_is_represented(self, realistic_org):
        assert set(
            Employee.objects.values_list("currency", flat=True).distinct()
        ) == set(Currency.values)

    def test_country_and_currency_agree(self, realistic_org):
        """An Indian employee paid in yen would be a seeding bug."""
        pairs = set(
            Employee.objects.values_list("country", "currency").distinct()
        )
        by_country = {}
        for country, currency in pairs:
            by_country.setdefault(country, set()).add(currency)
        assert all(len(currencies) == 1 for currencies in by_country.values())


class TestJobTitleDrivesSalary:
    """Title is what makes /analytics/by-title show a seniority gradient."""

    def mean_usd(self, title):
        amounts = list(
            Employee.objects.filter(job_title=title).values_list(
                "salary_usd", flat=True
            )
        )
        assert amounts, f"no employees with title {title!r}"
        return statistics.mean(amounts)

    def test_seniority_gradient_within_engineering(self, realistic_org):
        assert (
            self.mean_usd("Junior Engineer")
            < self.mean_usd("Engineer")
            < self.mean_usd("Senior Engineer")
            < self.mean_usd("Staff Engineer")
        )

    def test_gradient_holds_within_a_single_country(self, realistic_org):
        """Country mix could otherwise explain the gradient away."""

        def mean_for(title):
            amounts = list(
                Employee.objects.filter(
                    job_title=title, country="US"
                ).values_list("salary_amount", flat=True)
            )
            assert amounts, title
            return statistics.mean(amounts)

        assert mean_for("Junior Engineer") < mean_for("Senior Engineer")

    def test_titles_span_several_departments(self, realistic_org):
        assert Employee.objects.values("department").distinct().count() >= 8

    def test_each_department_uses_its_own_titles(self, realistic_org):
        engineering = set(
            Employee.objects.filter(department="Engineering").values_list(
                "job_title", flat=True
            )
        )
        finance = set(
            Employee.objects.filter(department="Finance").values_list(
                "job_title", flat=True
            )
        )
        assert engineering and finance
        assert not engineering & finance


class TestFlush:
    def test_flush_replaces_rather_than_appends(self, db):
        seed_employees(30)
        seed_employees(30, flush=True)
        assert Employee.objects.count() == 30

    def test_seeding_over_existing_data_is_refused(self, db):
        """Employee codes would collide. Fail with an instruction, not an
        IntegrityError from three frames down."""
        seed_employees(10)
        with pytest.raises(SeedError, match="--flush"):
            seed_employees(10)

    def test_flush_clears_salary_history_too(self, db):
        seed_employees(5)
        employee = Employee.objects.first()
        SalaryChange.objects.create(
            employee=employee,
            old_amount=Decimal("1.00"),
            old_currency=employee.currency,
            new_amount=Decimal("2.00"),
            new_currency=employee.currency,
            changed_by="test",
        )
        seed_employees(5, flush=True)
        assert SalaryChange.objects.count() == 0


class TestSeedCreatesNothingElse:
    def test_no_users_are_created(self, db):
        """Authentication is out of scope (REQUIREMENTS.md section 6), so the
        seed creates employees and rates and nothing else."""
        seed_employees(50)
        assert get_user_model().objects.count() == 0

    def test_no_salary_history_is_invented(self, db):
        """Seeded employees have a starting salary, not a change."""
        seed_employees(50)
        assert SalaryChange.objects.count() == 0


class TestWritesAreBatched:
    """Query count is the deterministic proxy for speed.

    A wall-clock assertion would be flaky on shared CI, so the suite pins the
    query count and the real timings are measured once and recorded in
    docs/DECISIONS.md.
    """

    @staticmethod
    def queries_for(count):
        """Queries spent inserting `count` rows.

        The clear-down happens outside the capture on purpose: deleting 2,000
        rows costs more queries than deleting 200 (SQLite chunks the IN
        clause), which would swamp the insert cost this is measuring.
        """
        Employee.objects.all().delete()
        with CaptureQueriesContext(connection) as captured:
            seed_employees(count)
        return len(captured)

    def test_writes_are_batched_not_per_row(self, db):
        """2,000 rows must cost far fewer than 2,000 statements."""
        assert self.queries_for(2000) < 100

    def test_rows_per_query_improves_with_scale(self, db):
        """The portable property.

        An earlier version asserted that ten times the rows cost at most one
        extra query, which is true on Postgres and false here: SQLite caps
        parameters per statement at 999, so with Employee's 13 columns
        bulk_create batches about 76 rows regardless of batch_size=1000.
        Postgres allows 65,535, where the configured 1,000 governs and 10,000
        rows really is ten statements.

        What holds on both is that batching amortises: rows per query rises
        with the row count instead of staying flat at one.
        """
        self.queries_for(10)  # warm-up: loads the FX fixture once
        small = 200 / self.queries_for(200)
        large = 2000 / self.queries_for(2000)
        assert large > small, (small, large)


class TestManagementCommand:
    def test_seeds_the_requested_count(self, db):
        call_command("seed", "--count", "40", verbosity=0)
        assert Employee.objects.count() == 40

    def test_defaults_to_ten_thousand(self, db):
        from apps.core.management.commands.seed import DEFAULT_COUNT

        assert DEFAULT_COUNT == 10_000

    def test_flush_flag_is_wired(self, db):
        call_command("seed", "--count", "10", verbosity=0)
        call_command("seed", "--count", "10", "--flush", verbosity=0)
        assert Employee.objects.count() == 10

    def test_seed_flag_is_wired(self, db):
        call_command("seed", "--count", "20", "--seed", "7", verbosity=0)
        first = business_rows()
        call_command("seed", "--count", "20", "--seed", "7", "--flush", verbosity=0)
        assert business_rows() == first

    def test_refusing_to_overwrite_raises_a_command_error(self, db):
        from django.core.management.base import CommandError

        call_command("seed", "--count", "5", verbosity=0)
        with pytest.raises(CommandError, match="--flush"):
            call_command("seed", "--count", "5", verbosity=0)


class TestIfEmpty:
    """The release command runs on every deploy.

    It must populate a fresh database and then keep quiet, without the
    operator having to remember which deploy is the first one.
    """

    def test_seeds_a_fresh_database(self, db):
        assert seed_employees(20, if_empty=True) == 20
        assert Employee.objects.count() == 20

    def test_is_a_no_op_when_employees_exist(self, db):
        seed_employees(20)
        assert seed_employees(20, if_empty=True) == 0
        assert Employee.objects.count() == 20

    def test_does_not_raise_when_it_skips(self, db):
        """Unlike a bare re-seed, which refuses. A deploy must not fail
        merely because the database is already populated."""
        seed_employees(5)
        seed_employees(5, if_empty=True)  # no exception

    def test_leaves_existing_rows_untouched(self, db):
        seed_employees(20)
        before = business_rows()
        seed_employees(20, if_empty=True)
        assert business_rows() == before

    def test_still_ensures_fx_rates_when_it_skips(self, db):
        """Rates could be missing even when employees are not."""
        seed_employees(5)
        FxRate.objects.all().delete()
        seed_employees(5, if_empty=True)
        assert FxRate.objects.count() == len(Currency.values)

    def test_conflicts_with_flush(self, db):
        """One says replace everything, the other says touch nothing."""
        with pytest.raises(SeedError, match="--flush"):
            seed_employees(5, if_empty=True, flush=True)

    def test_command_flag_is_wired(self, db):
        call_command("seed", "--count", "10", verbosity=0)
        call_command("seed", "--count", "10", "--if-empty", verbosity=0)
        assert Employee.objects.count() == 10
