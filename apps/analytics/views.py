"""Read-only analytics endpoints.

Thin: each view names a grouping and hands to apps.analytics.services. All
figures are USD.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.serializers import (
    SalaryByGroupSerializer,
    SalarySummarySerializer,
)
from apps.analytics.services import salary_by, salary_summary


@extend_schema(responses=SalarySummarySerializer)
class SalarySummaryView(APIView):
    """Headcount and cost across the whole org, in USD."""

    def get(self, request):
        return Response(SalarySummarySerializer(salary_summary()).data)


class BaseSalaryByView(APIView):
    """Per-group pay statistics. Subclasses name the column."""

    group_field: str

    def get(self, request):
        rows = salary_by(self.group_field)
        return Response(SalaryByGroupSerializer(rows, many=True).data)


@extend_schema(responses=SalaryByGroupSerializer(many=True))
class SalaryByCountryView(BaseSalaryByView):
    group_field = "country"


@extend_schema(responses=SalaryByGroupSerializer(many=True))
class SalaryByDepartmentView(BaseSalaryByView):
    group_field = "department"


@extend_schema(responses=SalaryByGroupSerializer(many=True))
class SalaryByTitleView(BaseSalaryByView):
    group_field = "job_title"
