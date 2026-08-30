"""Add job_title to Employee.

The confirmed schema (docs/REQUIREMENTS.md section 4) includes Job Title. It
arrived with the Incubyte team's scope guidance, after 0001 had landed.

The column is NOT NULL with no model-level default, so the one-off default here
exists only to backfill rows written before this migration. `preserve_default`
is False, so nothing after this point may omit a job title.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="job_title",
            field=models.CharField(
                default="Unassigned",
                help_text="Role title; also an analytics grouping.",
                max_length=100,
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(
                fields=["job_title"], name="employee_job_title_idx"
            ),
        ),
    ]
