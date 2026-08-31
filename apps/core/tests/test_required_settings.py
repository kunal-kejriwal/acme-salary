"""Production refuses to start on a partial configuration, and says why.

Written after a real deploy failed on DJANGO_SECRET_KEY and would have failed
three more times -- once per remaining variable -- had they been added one at
a time.
"""

from config.settings.required import (
    REQUIRED_IN_PRODUCTION,
    describe_missing,
    missing_settings,
)

COMPLETE = {
    "DJANGO_SECRET_KEY": "a-real-key",
    "DJANGO_ALLOWED_HOSTS": "api.example.com",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "DATABASE_URL": "postgres://u:p@host:5432/d",
}


class TestMissingSettings:
    def test_complete_configuration_reports_nothing(self):
        assert missing_settings(COMPLETE) == []

    def test_absent_variable_is_reported(self):
        environ = {k: v for k, v in COMPLETE.items() if k != "DJANGO_SECRET_KEY"}
        assert missing_settings(environ) == ["DJANGO_SECRET_KEY"]

    def test_blank_variable_counts_as_missing(self):
        """An empty string is a configuration mistake, not a value."""
        assert missing_settings({**COMPLETE, "DATABASE_URL": ""}) == ["DATABASE_URL"]

    def test_whitespace_only_counts_as_missing(self):
        assert missing_settings({**COMPLETE, "DJANGO_SECRET_KEY": "   "}) == [
            "DJANGO_SECRET_KEY"
        ]

    def test_all_missing_are_reported_together(self):
        """The point of the whole exercise.

        Reporting one at a time turns a single fix into one failed deploy per
        variable.
        """
        assert missing_settings({}) == list(REQUIRED_IN_PRODUCTION)

    def test_empty_environment_reports_every_requirement(self):
        assert len(missing_settings({})) == 4


class TestTheMessage:
    def test_names_every_missing_variable(self):
        message = describe_missing(missing_settings({}))
        for name in REQUIRED_IN_PRODUCTION:
            assert name in message

    def test_says_how_to_generate_a_secret_key(self):
        message = describe_missing(["DJANGO_SECRET_KEY"])
        assert "get_random_secret_key" in message

    def test_points_at_the_readme(self):
        assert "README" in describe_missing(["DATABASE_URL"])

    def test_singular_reads_correctly(self):
        assert "variable is missing" in describe_missing(["DATABASE_URL"])

    def test_plural_reads_correctly(self):
        assert "variables are missing" in describe_missing(
            ["DATABASE_URL", "DJANGO_SECRET_KEY"]
        )
