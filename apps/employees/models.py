import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from apps.core.constants import Currency

iso_3166_alpha_2 = RegexValidator(
    regex=r"^[A-Z]{2}$",
    message="Country must be an uppercase ISO 3166-1 alpha-2 code, e.g. IN.",
)


class Employee(models.Model):
    """A person on ACME's payroll.

    `salary_amount` + `currency` is the source of truth; `salary_usd` is a
    normalised copy written at the same time so cross-country aggregates are
    plain ORM aggregations (ARCHITECTURE.md section 3).

    Keeping those two in step is the service layer's job. `salary_usd` is
    deliberately NOT NULL with no default so a write that bypasses
    apps.employees.services fails loudly instead of storing a silent zero.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee_code = models.CharField(
        max_length=32,
        unique=True,
        help_text="Human-readable identifier issued by HR.",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    country = models.CharField(
        max_length=2,
        validators=[iso_3166_alpha_2],
        help_text="ISO 3166-1 alpha-2 code.",
    )
    joined_on = models.DateField()

    salary_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Gross annual salary in the employee's local currency.",
    )
    currency = models.CharField(max_length=3, choices=Currency.choices)
    salary_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="salary_amount normalised to USD at write time.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Matches the (last_name, first_name) index, so paging through the
        # list view stays cheap and the order is stable.
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["country"], name="employee_country_idx"),
            models.Index(fields=["department"], name="employee_department_idx"),
            models.Index(
                fields=["last_name", "first_name"], name="employee_name_idx"
            ),
        ]
        constraints = [
            # Enforced by the database, so it holds for bulk_create and raw
            # writes too -- not just for paths that call full_clean().
            models.CheckConstraint(
                condition=models.Q(salary_amount__gte=0),
                name="employee_salary_amount_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.employee_code})"


class SalaryChange(models.Model):
    """Append-only audit trail of salary movements.

    Written by apps.employees.services on every salary update. Nothing here
    is ever updated or deleted except by cascade when the employee goes.

    Currency is recorded on both sides, which extends the ERD in
    ARCHITECTURE.md section 3. That diagram has a single `currency` column,
    but a move from 100000 INR to 2000 USD is a raise and would read as a 98%
    cut if both amounts were interpreted against one currency. See
    docs/DECISIONS.md.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary_changes",
    )

    old_amount = models.DecimalField(max_digits=14, decimal_places=2)
    old_currency = models.CharField(max_length=3, choices=Currency.choices)
    new_amount = models.DecimalField(max_digits=14, decimal_places=2)
    new_currency = models.CharField(max_length=3, choices=Currency.choices)

    changed_by = models.CharField(
        max_length=254,
        help_text="Username of the actor, or a system identifier for imports.",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(
                fields=["employee", "-changed_at"], name="salarychange_history_idx"
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.employee_id}: {self.old_amount} {self.old_currency} -> "
            f"{self.new_amount} {self.new_currency}"
        )
