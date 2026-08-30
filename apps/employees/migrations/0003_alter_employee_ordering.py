"""Append `id` to Employee's default ordering.

Surname and forename are not unique, so the previous ordering was partial:
tied rows came back in whatever order the database produced, and under
pagination a tie straddling a page boundary can show a row twice or skip it.
`id` closes the order off.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0002_employee_job_title"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="employee",
            options={"ordering": ["last_name", "first_name", "id"]},
        ),
    ]
