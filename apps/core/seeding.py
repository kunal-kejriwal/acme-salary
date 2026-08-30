"""Deterministic generation of a realistic ACME org.

This is how the 10,000 records are populated (REQUIREMENTS.md §3). Two
properties matter, and they pull in different directions:

**Deterministic.** Same seed, same data, every run -- including primary keys.
A reproducible dataset that renumbers itself is only half reproducible.
Salary draws come from a plain `random.Random` rather than Faker's generator,
so a Faker upgrade can change the names without moving a single salary.

**Realistic in local currency.** Salary is driven by (country, job title), not
by one global number range. 80,000 is a reasonable USD salary, about 960 USD
in INR, and about 510 USD in JPY. Seeding every country from the same
distribution would make the dashboard look fake and would make the whole USD
normalisation pointless, since every figure would already be comparable.

Job title drives the multiplier, which is what gives `/analytics/by-title` a
visible seniority gradient -- the chart that best answers "how does this org
pay people".
"""

import datetime as dt
import math
import random
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.core.management import call_command
from django.db import transaction
from faker import Faker

from apps.core.constants import Currency
from apps.core.models import FxRate
from apps.core.services import rate_map, to_usd
from apps.employees.models import Employee

BATCH_SIZE = 1000
DEFAULT_SEED = 42


class SeedError(RuntimeError):
    """The seed cannot run as asked."""


class Country:
    """Where ACME operates: ISO code, currency, Faker locale, staff share."""

    def __init__(self, code, currency, locale, weight, base_salary, rounding):
        self.code = code
        self.currency = currency
        self.locale = locale
        self.weight = weight
        #: Local-currency salary for a mid-level individual contributor.
        self.base_salary = Decimal(base_salary)
        #: Salaries are quoted in round numbers, and the round unit differs
        #: wildly: nobody advertises a JPY salary to the nearest 100.
        self.rounding = Decimal(rounding)


COUNTRIES = [
    Country("US", "USD", "en_US", 0.26, "120000", "500"),
    Country("IN", "INR", "en_IN", 0.24, "1800000", "10000"),
    Country("GB", "GBP", "en_GB", 0.12, "62000", "500"),
    Country("DE", "EUR", "de_DE", 0.11, "68000", "500"),
    Country("BR", "BRL", "pt_BR", 0.09, "130000", "1000"),
    Country("JP", "JPY", "ja_JP", 0.07, "6800000", "100000"),
    Country("SG", "SGD", "en_US", 0.06, "90000", "500"),
    Country("AU", "AUD", "en_AU", 0.05, "105000", "500"),
]

#: Department -> [(job title, salary multiplier relative to a mid-level IC)].
#: Titles do not repeat across departments, so a title identifies a job.
DEPARTMENTS = {
    "Engineering": [
        ("Junior Engineer", 0.55),
        ("Engineer", 1.00),
        ("Senior Engineer", 1.45),
        ("Staff Engineer", 1.90),
        ("Engineering Manager", 2.05),
    ],
    "Data": [
        ("Data Analyst", 0.80),
        ("Data Scientist", 1.20),
        ("Senior Data Scientist", 1.60),
        ("Head of Data", 2.20),
    ],
    "Product": [
        ("Associate Product Manager", 0.75),
        ("Product Manager", 1.25),
        ("Senior Product Manager", 1.70),
        ("Director of Product", 2.30),
    ],
    "Design": [
        ("Product Designer", 0.95),
        ("Senior Product Designer", 1.35),
        ("Design Lead", 1.75),
    ],
    "Finance": [
        ("Financial Analyst", 0.80),
        ("Finance Manager", 1.30),
        ("Financial Controller", 1.80),
        ("Head of Finance", 2.40),
    ],
    "People": [
        ("Recruiter", 0.70),
        ("HR Business Partner", 1.05),
        ("People Operations Manager", 1.35),
        ("Head of People", 2.10),
    ],
    "Sales": [
        ("Sales Development Representative", 0.60),
        ("Account Executive", 1.10),
        ("Senior Account Executive", 1.50),
        ("Sales Director", 2.20),
    ],
    "Marketing": [
        ("Marketing Associate", 0.65),
        ("Marketing Manager", 1.15),
        ("Senior Marketing Manager", 1.55),
        ("Head of Marketing", 2.15),
    ],
    "Support": [
        ("Support Specialist", 0.60),
        ("Senior Support Specialist", 0.90),
        ("Support Team Lead", 1.20),
    ],
    "Legal": [
        ("Legal Counsel", 1.40),
        ("Senior Legal Counsel", 1.90),
        ("General Counsel", 2.60),
    ],
}

DEPARTMENT_WEIGHTS = {
    "Engineering": 0.30,
    "Sales": 0.12,
    "Support": 0.10,
    "Product": 0.08,
    "Data": 0.08,
    "Marketing": 0.08,
    "Finance": 0.07,
    "People": 0.07,
    "Design": 0.06,
    "Legal": 0.04,
}

#: Spread of pay within a single (country, title) cell. Log-normal, so the
#: tail runs upwards -- which is how salary bands actually behave.
SALARY_SIGMA = 0.16

#: Fixed hiring window. Deliberately not "today", so the data does not drift
#: with the calendar and tests stay reproducible.
HIRING_START = dt.date(2016, 1, 1)
HIRING_DAYS = 3_800


def ensure_fx_rates() -> None:
    """Load the FX fixture if any rate is missing.

    Without this a seed against a fresh database hits MissingRateError on row
    one. The fixture carries explicit primary keys, so re-loading updates in
    place rather than duplicating.
    """
    seeded = set(FxRate.objects.values_list("currency", flat=True))
    if set(Currency.values) - seeded:
        call_command("loaddata", "fx_rates", verbosity=0)


def _draw_salary(country: Country, multiplier: float, rng: random.Random) -> Decimal:
    """A local-currency salary for one person.

    Log-normal spread around the country's base for this seniority, rounded
    to a locally plausible unit.
    """
    spread = math.exp(rng.gauss(0.0, SALARY_SIGMA))
    raw = country.base_salary * Decimal(str(multiplier)) * Decimal(str(spread))

    steps = (raw / country.rounding).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    salary = max(steps, Decimal("1")) * country.rounding
    return salary.quantize(Decimal("0.01"))


def _build_employee(index, rng, fakers, rates):
    country = rng.choices(COUNTRIES, weights=[c.weight for c in COUNTRIES])[0]

    department = rng.choices(
        list(DEPARTMENT_WEIGHTS), weights=list(DEPARTMENT_WEIGHTS.values())
    )[0]
    job_title, multiplier = rng.choice(DEPARTMENTS[department])

    salary_amount = _draw_salary(country, multiplier, rng)
    faker = fakers[country.locale]

    return Employee(
        # Drawn from the seeded RNG rather than uuid4, so the whole dataset
        # -- keys included -- reproduces exactly.
        id=uuid.UUID(int=rng.getrandbits(128), version=4),
        employee_code=f"ACME-{index:05d}",
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        department=department,
        job_title=job_title,
        country=country.code,
        joined_on=HIRING_START + dt.timedelta(days=rng.randint(0, HIRING_DAYS)),
        salary_amount=salary_amount,
        currency=country.currency,
        salary_usd=to_usd(salary_amount, country.currency, rates=rates),
    )


@transaction.atomic
def seed_employees(
    count: int, *, seed: int = DEFAULT_SEED, flush: bool = False
) -> int:
    """Create `count` employees. Returns how many landed.

    Creates employees and FX rates. Nothing else -- no users: authentication
    is out of scope (REQUIREMENTS.md §7).
    """
    if count < 0:
        raise SeedError(f"count must be zero or more, got {count}.")

    ensure_fx_rates()

    if flush:
        Employee.objects.all().delete()  # cascades to salary history
    elif Employee.objects.exists():
        raise SeedError(
            "The database already holds employees and their codes would "
            "collide. Re-run with --flush to replace them."
        )

    rng = random.Random(seed)
    fakers = {}
    for country in COUNTRIES:
        if country.locale not in fakers:
            faker = Faker(country.locale)
            faker.seed_instance(seed)
            fakers[country.locale] = faker

    rates = rate_map()

    employees = [
        _build_employee(index, rng, fakers, rates)
        for index in range(1, count + 1)
    ]
    Employee.objects.bulk_create(employees, batch_size=BATCH_SIZE)
    return len(employees)
