from django.contrib import admin

from apps.employees.models import Employee, SalaryChange


class SalaryChangeInline(admin.TabularInline):
    """Read-only: the trail is append-only and belongs to the service."""

    model = SalaryChange
    extra = 0
    can_delete = False
    readonly_fields = [
        "old_amount",
        "old_currency",
        "new_amount",
        "new_currency",
        "changed_by",
        "changed_at",
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        "employee_code",
        "last_name",
        "first_name",
        "department",
        "job_title",
        "country",
        "salary_amount",
        "currency",
        "salary_usd",
    ]
    list_filter = ["country", "department", "currency"]
    search_fields = ["employee_code", "first_name", "last_name"]
    # salary_usd is derived; editing it here would desync it from the salary.
    readonly_fields = ["salary_usd", "created_at", "updated_at"]
    inlines = [SalaryChangeInline]


@admin.register(SalaryChange)
class SalaryChangeAdmin(admin.ModelAdmin):
    list_display = [
        "employee",
        "old_amount",
        "old_currency",
        "new_amount",
        "new_currency",
        "changed_by",
        "changed_at",
    ]
    list_filter = ["new_currency", "changed_at"]
    search_fields = ["employee__employee_code", "changed_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
