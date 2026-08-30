"""Serializers for the employees API.

Normalisation belongs here, at the edge. `core.to_usd` is deliberately strict
about currency codes so that a bad code in a data pipeline surfaces instead of
being guessed at; that strictness should not leak out as a surprise for API
consumers who send "inr". The rule is: be forgiving at the boundary, exact
underneath.
"""

from rest_framework import serializers

from apps.employees.models import Employee, SalaryChange


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "first_name",
            "last_name",
            "department",
            "job_title",
            "country",
            "joined_on",
            "salary_amount",
            "currency",
            "salary_usd",
            "created_at",
            "updated_at",
        ]
        # salary_usd is derived from salary_amount and the FX table. Accepting
        # it from a client would let them state a figure that contradicts the
        # salary it is supposed to normalise.
        read_only_fields = ["id", "salary_usd", "created_at", "updated_at"]

    def to_internal_value(self, data):
        """Upper-case the code fields before field validation runs.

        This has to happen here rather than in `validate_currency`, because
        ChoiceField rejects "eur" before any `validate_<field>` hook is
        reached.
        """
        data = data.copy() if hasattr(data, "copy") else dict(data)
        for field in ("currency", "country"):
            value = data.get(field)
            if isinstance(value, str):
                data[field] = value.strip().upper()
        return super().to_internal_value(data)


class SalaryChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryChange
        fields = [
            "id",
            "old_amount",
            "old_currency",
            "new_amount",
            "new_currency",
            "changed_by",
            "changed_at",
        ]
        read_only_fields = fields
