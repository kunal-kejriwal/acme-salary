"""Filters for the employee list view.

The salary range filters deliberately target `salary_usd`, never
`salary_amount`. See the class docstring below -- this is the one filter where
picking the obvious column would produce answers that look fine and mean
nothing.
"""

import django_filters

from apps.employees.models import Employee


class EmployeeFilter(django_filters.FilterSet):
    """Server-side filtering for GET /employees.

    `salary_usd_min` and `salary_usd_max` filter on the normalised USD column.

    Filtering on `salary_amount` would compare raw numbers across currencies:
    a 1,000,000 INR salary (about 12,000 USD) and a 1,000,000 GBP salary
    (about 1,270,000 USD) would both match a "salary between 900k and 1.1m"
    query, and neither answer is what anyone asked. The whole point of
    normalising at write time (ARCHITECTURE.md section 3) is that a range
    query over mixed currencies is a plain indexed comparison.

    The parameter names say `usd` out loud so a caller cannot mistake which
    currency the bound is expressed in.
    """

    # NumberFilter uses forms.DecimalField, so bounds stay Decimal and money
    # never touches a float even on the query path.
    salary_usd_min = django_filters.NumberFilter(
        field_name="salary_usd",
        lookup_expr="gte",
        label="Minimum salary in USD",
    )
    salary_usd_max = django_filters.NumberFilter(
        field_name="salary_usd",
        lookup_expr="lte",
        label="Maximum salary in USD",
    )

    class Meta:
        model = Employee
        # Exact matches on the indexed columns from ARCHITECTURE.md section 8.
        fields = ["country", "department", "job_title", "currency"]
