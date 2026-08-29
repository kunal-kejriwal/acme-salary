"""The static FX rate table seeded from the in-repo fixture.

Rates are a deliberate point-in-time snapshot, not a live feed
(ARCHITECTURE.md section 9) — so they are asserted exactly.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.core.constants import Currency
from apps.core.models import FxRate

# Hand-checked against the fixture. USD per 1 unit of the currency.
EXPECTED_RATES = {
    "USD": Decimal("1.00000000"),
    "EUR": Decimal("1.08000000"),
    "GBP": Decimal("1.27000000"),
    "AUD": Decimal("0.66000000"),
    "SGD": Decimal("0.74000000"),
    "BRL": Decimal("0.18000000"),
    "INR": Decimal("0.01200000"),
    "JPY": Decimal("0.00640000"),
}


def test_fixture_seeds_a_rate_for_every_supported_currency(fx_rates):
    """A currency without a rate is unconvertible, so this must never drift."""
    seeded = set(FxRate.objects.values_list("currency", flat=True))
    assert seeded == set(Currency.values)


def test_fixture_rates_match_the_recorded_snapshot(fx_rates):
    for currency, expected in EXPECTED_RATES.items():
        rate = FxRate.objects.get(currency=currency)
        assert rate.usd_per_unit == expected, currency


def test_usd_converts_to_itself_exactly(fx_rates):
    assert FxRate.objects.get(currency="USD").usd_per_unit == Decimal("1")


def test_rates_are_decimal_not_float(fx_rates):
    for rate in FxRate.objects.all():
        assert isinstance(rate.usd_per_unit, Decimal)


def test_rates_are_positive(fx_rates):
    assert not FxRate.objects.filter(usd_per_unit__lte=0).exists()


def test_currency_is_unique(fx_rates):
    """One rate per currency — duplicates would make conversion ambiguous."""
    with pytest.raises(IntegrityError):
        FxRate.objects.create(currency="USD", usd_per_unit=Decimal("2"))


def test_str_is_readable(fx_rates):
    assert str(FxRate.objects.get(currency="INR")) == "1 INR = 0.01200000 USD"
