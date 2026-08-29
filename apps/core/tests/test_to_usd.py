"""Conversion of a salary amount into USD.

Every expected value here is hand-computed from the rates in
apps/core/fixtures/fx_rates.json, not read back out of the code.
"""

from decimal import Decimal

import pytest

from apps.core.constants import Currency
from apps.core.models import FxRate
from apps.core.services import MissingRateError, UnknownCurrencyError, to_usd


class TestConversionCorrectness:
    """Hand-computed against the fixture snapshot."""

    @pytest.mark.parametrize(
        ("amount", "currency", "expected"),
        [
            # 100000 INR * 0.012 = 1200
            ("100000.00", "INR", "1200.00"),
            # 50000 EUR * 1.08 = 54000
            ("50000.00", "EUR", "54000.00"),
            # 80000 GBP * 1.27 = 101600
            ("80000.00", "GBP", "101600.00"),
            # 120000 SGD * 0.74 = 88800
            ("120000.00", "SGD", "88800.00"),
            # 250000 BRL * 0.18 = 45000
            ("250000.00", "BRL", "45000.00"),
            # 5000000 JPY * 0.0064 = 32000
            ("5000000.00", "JPY", "32000.00"),
            # 95000 AUD * 0.66 = 62700
            ("95000.00", "AUD", "62700.00"),
        ],
    )
    def test_converts_at_the_seeded_rate(self, fx_rates, amount, currency, expected):
        assert to_usd(Decimal(amount), currency) == Decimal(expected)

    def test_usd_converts_to_itself(self, fx_rates):
        assert to_usd(Decimal("75000.00"), "USD") == Decimal("75000.00")

    def test_zero_converts_to_zero(self, fx_rates):
        assert to_usd(Decimal("0"), "INR") == Decimal("0.00")

    def test_accepts_the_currency_enum_as_well_as_a_string(self, fx_rates):
        assert to_usd(Decimal("100000.00"), Currency.INR) == Decimal("1200.00")

    def test_converts_negative_amounts(self, fx_rates):
        """to_usd is arithmetic, not policy.

        Rejecting negative salaries belongs to the employee and import
        validation, so this stays a pure conversion.
        """
        assert to_usd(Decimal("-100000.00"), "INR") == Decimal("-1200.00")


class TestDecimalPrecision:
    def test_result_is_a_decimal(self, fx_rates):
        assert isinstance(to_usd(Decimal("1"), "USD"), Decimal)

    def test_result_is_always_quantized_to_two_places(self, fx_rates):
        # 1 INR * 0.012 = 0.012, which has to land on a cent boundary.
        result = to_usd(Decimal("1"), "INR")
        assert result.as_tuple().exponent == -2
        assert result == Decimal("0.01")

    def test_rounds_half_up_not_half_even(self, fx_rates):
        """Decimal("0.005") is exactly half a cent.

        Banker's rounding would give 0.00; salary figures round up.
        """
        assert to_usd(Decimal("0.005"), "USD") == Decimal("0.01")

    def test_no_binary_float_drift(self, fx_rates):
        """The canonical float trap.

        2.675 is not representable in binary floating point -- it is stored as
        2.67499999..., so a float implementation rounds it down to 2.67.
        Decimal arithmetic gives the arithmetically correct 2.68.
        """
        assert to_usd(Decimal("2.675"), "USD") == Decimal("2.68")

    def test_precision_holds_at_salary_scale(self, fx_rates):
        # 999999999.99 JPY * 0.0064 = 6399999.999936 -> 6400000.00
        assert to_usd(Decimal("999999999.99"), "JPY") == Decimal("6400000.00")

    def test_rejects_float_input(self, fx_rates):
        """Floats must not get in: the drift would already have happened."""
        with pytest.raises(TypeError):
            to_usd(100000.00, "INR")

    def test_rejects_string_input(self, fx_rates):
        with pytest.raises(TypeError):
            to_usd("100000.00", "INR")

    def test_accepts_int_amounts(self, fx_rates):
        """int is exact, so it carries no drift risk."""
        assert to_usd(100000, "INR") == Decimal("1200.00")


class TestUnknownCurrency:
    def test_unsupported_code_raises(self, fx_rates):
        with pytest.raises(UnknownCurrencyError):
            to_usd(Decimal("100"), "ZAR")

    def test_nonsense_code_raises(self, fx_rates):
        with pytest.raises(UnknownCurrencyError):
            to_usd(Decimal("100"), "XYZ")

    def test_error_names_the_offending_code(self, fx_rates):
        with pytest.raises(UnknownCurrencyError, match="ZAR"):
            to_usd(Decimal("100"), "ZAR")

    def test_lowercase_code_is_rejected(self, fx_rates):
        """Normalising case belongs to the import layer, which sees raw CSV."""
        with pytest.raises(UnknownCurrencyError):
            to_usd(Decimal("100"), "inr")

    def test_supported_currency_with_no_seeded_rate_raises_missing_rate(self, fx_rates):
        """A different failure: valid input, misconfigured deployment."""
        FxRate.objects.filter(currency="INR").delete()
        with pytest.raises(MissingRateError, match="INR"):
            to_usd(Decimal("100"), "INR")
