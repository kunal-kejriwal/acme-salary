"""HTTP layer for the employees API.

Thin by design: each write hands straight to apps.employees.services, which
owns salary normalisation and the audit trail. Nothing here decides anything
about money.
"""

from rest_framework import viewsets

from apps.employees.filters import EmployeeFilter
from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer
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
