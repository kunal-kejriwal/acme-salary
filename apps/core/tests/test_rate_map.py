"""Bulk-friendly conversion: one rate lookup for a whole batch.

`to_usd` queries per call, which is right for a single-row write and wrong for
seeding 10,000 employees. `rate_map()` loads every rate once; `to_usd(...,
rates=...)` then converts without touching the database.
"""

from decimal import Decimal

import pytest

from apps.core.constants import Currency
from apps.core.models import FxRate
from apps.core.services import (
    MissingRateError,
    UnknownCurrencyError,
    rate_map,
    to_usd,
)


class TestRateMap:
    def test_contains_every_supported_currency(self, fx_rates):
        assert set(rate_map()) == set(Currency.values)

    def test_values_are_decimal(self, fx_rates):
        assert all(isinstance(rate, Decimal) for rate in rate_map().values())

    def test_matches_the_seeded_rates(self, fx_rates):
        assert rate_map()["INR"] == Decimal("0.01200000")

    def test_costs_a_single_query(self, fx_rates, django_assert_num_queries):
        with django_assert_num_queries(1):
            rate_map()


class TestConversionWithAPreloadedMap:
    def test_agrees_with_the_querying_path(self, fx_rates):
        rates = rate_map()
        for currency in Currency.values:
            amount = Decimal("100000.00")
            assert to_usd(amount, currency, rates=rates) == to_usd(amount, currency)

    def test_converts_without_touching_the_database(
        self, fx_rates, django_assert_num_queries
    ):
        """The whole point: a 10,000-row seed must not issue 10,000 queries."""
        rates = rate_map()
        with django_assert_num_queries(0):
            for _ in range(50):
                to_usd(Decimal("100000.00"), "INR", rates=rates)

    def test_hand_computed_value_is_unchanged(self, fx_rates):
        assert to_usd(Decimal("100000.00"), "INR", rates=rate_map()) == Decimal(
            "1200.00"
        )

    def test_rounding_is_unchanged(self, fx_rates):
        assert to_usd(Decimal("2.675"), "USD", rates=rate_map()) == Decimal("2.68")

    def test_still_rejects_floats(self, fx_rates):
        with pytest.raises(TypeError):
            to_usd(100000.00, "INR", rates=rate_map())


class TestErrorTaxonomyIsPreserved:
    """The preloaded path must fail the same way as the querying one.

    A bulk path that reports a different error for the same fault would send
    the reader somewhere else entirely.
    """

    def test_unsupported_currency_raises_unknown_currency(self, fx_rates):
        with pytest.raises(UnknownCurrencyError, match="ZAR"):
            to_usd(Decimal("100"), "ZAR", rates=rate_map())

    def test_supported_currency_absent_from_the_map_raises_missing_rate(
        self, fx_rates
    ):
        rates = rate_map()
        del rates["INR"]
        with pytest.raises(MissingRateError, match="INR"):
            to_usd(Decimal("100"), "INR", rates=rates)

    def test_empty_map_raises_missing_rate_not_unknown_currency(self, fx_rates):
        with pytest.raises(MissingRateError):
            to_usd(Decimal("100"), "USD", rates={})

    def test_map_is_empty_on_a_virgin_database(self, db):
        """No fixture loaded, so nothing to convert with."""
        FxRate.objects.all().delete()
        assert rate_map() == {}
