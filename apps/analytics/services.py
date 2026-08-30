"""Aggregate queries behind service functions.

Everything is reported in USD, read off the materialised `salary_usd` column,
so no conversion happens at read time (ARCHITECTURE.md section 3).

Each public function costs two queries regardless of how many groups come
back: one GROUP BY aggregate, and one window query that returns only the
middle one or two salaries per group. Neither scales with group count, which
is the property that matters -- a per-group median would be one query per job
title.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count, F, Max, Min, Sum, Window
from django.db.models.functions import RowNumber

from apps.employees.models import Employee

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")

#: What the API is allowed to group by. Each is indexed (ARCHITECTURE.md
#: section 7); an unindexed grouping would be a full scan per request.
GROUPABLE_FIELDS = ("country", "department", "job_title")


def _money(value) -> Decimal:
    """Coalesce and round to the cent.

    An empty table aggregates to None rather than zero, and SQLite computes
    AVG in floating point before Django casts it back, so the quantize is
    doing real work rather than cosmetics.
    """
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def _middle_salaries(group_field: str | None):
    """The middle one or two salaries per group, in a single query.

    SQLite has no `percentile_cont`, so the median is built from portable
    window functions: rank each row within its group by salary, count the
    group, and keep the rows whose rank is (n+1)//2 or (n+2)//2. That is the
    single middle row when the group is odd-sized and the two straddling rows
    when it is even.

    Integer division truncates identically on SQLite and PostgreSQL, so the
    same expression is correct on both.

    The averaging of the one or two survivors happens in Python, deliberately.
    It cannot be folded into this query: Django applies a window filter
    *after* GROUP BY, so adding an aggregate here silently groups by
    (group, salary) and returns one row per employee. Averaging two Decimals
    in Python is also exact, where SQLite's AVG would route the value through
    a float.
    """
    partition = [F(group_field)] if group_field else None

    queryset = Employee.objects.annotate(
        _rank=Window(
            RowNumber(),
            partition_by=partition,
            order_by=F("salary_usd").asc(),
        ),
        _size=Window(Count("id"), partition_by=partition),
    ).filter(
        _rank__gte=(F("_size") + 1) / 2,
        _rank__lte=(F("_size") + 2) / 2,
    )

    if group_field is None:
        return queryset.values_list("salary_usd", flat=True)
    return queryset.values_list(group_field, "salary_usd")


def _median_of(values) -> Decimal:
    values = list(values)
    if not values:
        return ZERO
    return _money(sum(values) / Decimal(len(values)))


def salary_summary() -> dict:
    """Org-wide headcount and cost, in USD."""
    totals = Employee.objects.aggregate(
        headcount=Count("id"),
        total=Sum("salary_usd"),
        average=Avg("salary_usd"),
    )
    return {
        "headcount": totals["headcount"],
        "total_usd": _money(totals["total"]),
        "average_usd": _money(totals["average"]),
        "median_usd": _median_of(_middle_salaries(None)),
    }


def salary_by(group_field: str) -> list[dict]:
    """Per-group pay statistics, heaviest group first.

    Groups are keyed as `group` rather than by the field name, so the three
    breakdowns share one response shape and the dashboard can render them all
    through one component.
    """
    if group_field not in GROUPABLE_FIELDS:
        raise ValueError(
            f"{group_field!r} is not groupable. "
            f"Expected one of: {', '.join(GROUPABLE_FIELDS)}."
        )

    medians: dict[str, list[Decimal]] = {}
    for group, salary in _middle_salaries(group_field):
        medians.setdefault(group, []).append(salary)

    rows = (
        Employee.objects.values(group_field)
        .annotate(
            headcount=Count("id"),
            average=Avg("salary_usd"),
            minimum=Min("salary_usd"),
            maximum=Max("salary_usd"),
        )
        # Explicit ordering is load-bearing, not decoration: without it
        # Employee.Meta.ordering leaks into the GROUP BY and silently groups
        # by (field, last_name, first_name, id) -- one row per employee.
        # The group name breaks headcount ties so the dashboard's bars do not
        # reshuffle between reloads.
        .order_by("-headcount", group_field)
    )

    return [
        {
            "group": row[group_field],
            "headcount": row["headcount"],
            "average_usd": _money(row["average"]),
            "median_usd": _median_of(medians.get(row[group_field], [])),
            "min_usd": _money(row["minimum"]),
            "max_usd": _money(row["maximum"]),
        }
        for row in rows
    ]
