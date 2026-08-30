"""Analytics routes, mounted under /api/v1."""

from django.urls import path

from apps.analytics.views import (
    SalaryByCountryView,
    SalaryByDepartmentView,
    SalaryByTitleView,
    SalarySummaryView,
)

urlpatterns = [
    path("analytics/summary/", SalarySummaryView.as_view(), name="analytics-summary"),
    path(
        "analytics/by-country/",
        SalaryByCountryView.as_view(),
        name="analytics-by-country",
    ),
    path(
        "analytics/by-department/",
        SalaryByDepartmentView.as_view(),
        name="analytics-by-department",
    ),
    path("analytics/by-title/", SalaryByTitleView.as_view(), name="analytics-by-title"),
]
