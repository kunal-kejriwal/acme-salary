"""Response shapes for the analytics endpoints.

DecimalField coerces to a string, which is what keeps money out of JSON's
float representation -- the same rule the employees API follows.
"""

from rest_framework import serializers


class SalarySummarySerializer(serializers.Serializer):
    headcount = serializers.IntegerField()
    # Total across 10,000 salaries needs room well beyond a single salary.
    total_usd = serializers.DecimalField(max_digits=20, decimal_places=2)
    average_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    median_usd = serializers.DecimalField(max_digits=14, decimal_places=2)


class SalaryByGroupSerializer(serializers.Serializer):
    group = serializers.CharField()
    headcount = serializers.IntegerField()
    average_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    median_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    min_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    max_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
