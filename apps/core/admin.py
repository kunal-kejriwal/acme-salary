from django.contrib import admin

from apps.core.models import FxRate


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ["currency", "usd_per_unit"]
    ordering = ["currency"]
