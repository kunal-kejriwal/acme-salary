"""HTTP layer for the employees API.

Thin by design: each write hands straight to apps.employees.services, which
owns salary normalisation and the audit trail. Nothing here decides anything
about money.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.employees.filters import EmployeeFilter
from apps.employees.models import Employee
from apps.employees.serializers import (
    EmployeeSerializer,
    SalaryChangeSerializer,
)
from apps.employees.services import (
    create_employee,
    delete_employee,
    update_employee,
)


class EmployeeViewSet(viewsets.ModelViewSet):
    """CRUD for employees."""

    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    filterset_class = EmployeeFilter

    # Free-text search covers who the person is, not where they sit --
    # department and job title have their own exact filters, and folding them
    # into search would make "Finance" match both a name and a department.
    search_fields = ["first_name", "last_name", "employee_code"]

    ordering_fields = [
        "last_name",
        "first_name",
        "job_title",
        "department",
        "country",
        "salary_usd",
        "joined_on",
        "employee_code",
    ]

    def perform_create(self, serializer):
        serializer.instance = create_employee(**serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = update_employee(
            serializer.instance,
            changed_by=self.request.user.get_username(),
            **serializer.validated_data,
        )

    def perform_destroy(self, instance):
        delete_employee(instance)

    @extend_schema(responses=SalaryChangeSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="salary-history")
    def salary_history(self, request, pk=None):
        """The append-only audit trail for one employee, newest first.

        Paginated like every other list in this API: an employee can
        accumulate changes indefinitely, and the History tab should not be
        the one place that loads without a bound.
        """
        changes = self.get_object().salary_changes.all()

        page = self.paginate_queryset(changes)
        serializer = SalaryChangeSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
