"""HTTP layer for the employees API.

Thin by design: each write hands straight to apps.employees.services, which
owns salary normalisation and the audit trail. Nothing here decides anything
about money.
"""

from rest_framework import viewsets

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

    # Phase 3 builds out the full filter, search and ordering surface. These
    # cover job_title only, which the confirmed schema added.
    filterset_fields = ["job_title"]
    ordering_fields = ["job_title", "last_name", "salary_usd", "joined_on"]

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
