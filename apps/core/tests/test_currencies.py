"""The set of currencies ACME pays salaries in."""

from apps.core.constants import Currency

EXPECTED_CODES = {"INR", "USD", "GBP", "EUR", "SGD", "BRL", "JPY", "AUD"}


def test_exactly_the_eight_supported_currencies():
    assert set(Currency.values) == EXPECTED_CODES


def test_codes_are_iso_4217_uppercase_alpha_3():
    for code in Currency.values:
        assert len(code) == 3
        assert code.isupper()
        assert code.isalpha()


def test_every_currency_has_a_human_readable_label():
    for currency in Currency:
        assert currency.label
        assert currency.label != currency.value


def test_usd_is_available_as_the_reporting_currency():
    """Analytics report in USD, so it has to be one of the choices."""
    assert Currency.USD == "USD"
