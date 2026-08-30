"""Money conversion for the core app.

Views stay thin; everything testable lives here (CLAUDE.md, "thin views, fat
services").

Money is Decimal end to end. Floats are rejected at the boundary rather than
quietly converted, because by the time a float reaches this function the
precision has already been lost.
"""

from decimal import ROUND_HALF_UP, Decimal

from apps.core.constants import Currency
from apps.core.models import FxRate

#: Salary figures are reported to the cent.
USD_QUANTUM = Decimal("0.01")

#: A preloaded {currency: usd_per_unit} mapping, as returned by `rate_map`.
RateMap = dict[str, Decimal]


class FxError(ValueError):
    """Base class for conversion failures."""


class UnknownCurrencyError(FxError):
    """The currency code is not one ACME supports.

    Bad input data -- the caller passed something outside `Currency`.
    """


class MissingRateError(FxError):
    """A supported currency has no seeded FX rate.

    Not a data problem but a deployment one: the fx_rates fixture has not been
    loaded, or a currency was added without a rate.
    """


def rate_map() -> RateMap:
    """Load every FX rate in one query.

    For bulk work. `get_rate` costs a query per call, which is fine for a
    single-row write and ruinous for a 10,000-row seed. Callers hold the
    result for the duration of a batch and pass it to `to_usd(rates=...)`.

    Deliberately returns whatever is in the table rather than validating
    completeness, so the caller decides whether a gap is fatal. `to_usd`
    raises `MissingRateError` for a currency the map does not cover.
    """
    return dict(FxRate.objects.values_list("currency", "usd_per_unit"))


def _validate_currency(currency: str | Currency) -> str:
    code = str(currency)
    if code not in Currency.values:
        raise UnknownCurrencyError(
            f"{code!r} is not a supported currency. "
            f"Supported: {', '.join(sorted(Currency.values))}."
        )
    return code


def get_rate(currency: str | Currency) -> Decimal:
    """Return the USD value of one unit of `currency`.

    Raises UnknownCurrencyError for an unsupported code and MissingRateError
    when a supported code has no seeded rate.
    """
    code = _validate_currency(currency)
    try:
        return FxRate.objects.get(currency=code).usd_per_unit
    except FxRate.DoesNotExist:
        raise MissingRateError(
            f"No FX rate seeded for {code!r}. Run `manage.py loaddata fx_rates`."
        ) from None


def to_usd(
    amount: Decimal | int,
    currency: str | Currency,
    *,
    rates: RateMap | None = None,
) -> Decimal:
    """Convert `amount` in `currency` to USD, rounded to the cent.

    Rounds half up: half a cent belongs to the employee, and banker's rounding
    would make the result depend on the parity of the preceding digit.

    `amount` must be Decimal or int. Floats and strings raise TypeError.

    Pass `rates` (from `rate_map()`) to convert without a query -- the bulk
    path. The error taxonomy is identical either way: an unsupported code is
    still UnknownCurrencyError, a supported code with no rate is still
    MissingRateError.
    """
    # bool is an int subclass, and a boolean salary is a bug worth surfacing.
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int)):
        raise TypeError(
            f"amount must be Decimal or int, got {type(amount).__name__}. "
            f"Floats are rejected because they cannot represent money exactly."
        )

    if rates is None:
        rate = get_rate(currency)
    else:
        code = _validate_currency(currency)
        try:
            rate = rates[code]
        except KeyError:
            raise MissingRateError(
                f"No FX rate loaded for {code!r}. "
                f"Run `manage.py loaddata fx_rates`."
            ) from None

    return (Decimal(amount) * rate).quantize(USD_QUANTUM, rounding=ROUND_HALF_UP)
