from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.constants import Currency


class FxRate(models.Model):
    """A point-in-time FX rate used to normalise salaries to USD.

    Deliberately static and seeded from `fixtures/fx_rates.json` rather than
    fetched from a live feed: it keeps conversion deterministic and testable
    (ARCHITECTURE.md section 9). The staleness trade-off is documented in
    docs/DECISIONS.md.

    `usd_per_unit` reads as "1 unit of `currency` is worth this many USD", so
    conversion is a multiplication and never a division.
    """

    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        unique=True,
        help_text="ISO 4217 code.",
    )
    usd_per_unit = models.DecimalField(
        max_digits=18,
        # JPY sits near 0.0064 USD, so 2 or 4 places would round it to nothing.
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
        help_text="USD value of one unit of this currency.",
    )

    class Meta:
        ordering = ["currency"]
        verbose_name = "FX rate"
        verbose_name_plural = "FX rates"

    def __str__(self) -> str:
        return f"1 {self.currency} = {self.usd_per_unit} USD"
