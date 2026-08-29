"""Shared domain constants.

Kept out of models.py so apps can import the currency enum without pulling in
the model layer.
"""

from django.db import models


class Currency(models.TextChoices):
    """ISO 4217 codes for the currencies ACME pays salaries in.

    USD doubles as the reporting currency: every analytics figure is expressed
    in it (ARCHITECTURE.md section 4).
    """

    INR = "INR", "Indian Rupee"
    USD = "USD", "US Dollar"
    GBP = "GBP", "Pound Sterling"
    EUR = "EUR", "Euro"
    SGD = "SGD", "Singapore Dollar"
    BRL = "BRL", "Brazilian Real"
    JPY = "JPY", "Japanese Yen"
    AUD = "AUD", "Australian Dollar"


#: Every salary figure is normalised to this currency before aggregation.
REPORTING_CURRENCY = Currency.USD
