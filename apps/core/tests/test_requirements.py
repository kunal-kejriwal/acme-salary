"""The production manifest is flat, pinned, and covers the deploy path.

Written after a deploy failed: `manage.py seed` runs in the release command,
apps/core/seeding.py imports faker at module level, and faker was listed only
in the development requirements. The suite was green throughout -- the tests
run where faker is installed, so nothing local could have caught it. These
assertions watch the file instead.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "requirements.txt"
DEVELOPMENT = ROOT / "requirements" / "dev.txt"


def requirement_lines(path: Path) -> list[str]:
    """Dependency lines only: no comments, includes or blanks."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-"))
    ]


class TestProductionManifest:
    def test_exists_at_the_repository_root(self):
        """Where build tools look for it."""
        assert PRODUCTION.is_file()

    def test_is_flat(self):
        """No `-r` includes.

        The manifest a builder reads should carry the list, not a pointer to
        another file it may or may not resolve.
        """
        includes = [
            line
            for line in PRODUCTION.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("-r", "--requirement"))
        ]
        assert includes == []

    def test_every_dependency_is_exactly_pinned(self):
        """A deploy should install what was tested."""
        unpinned = [line for line in requirement_lines(PRODUCTION) if "==" not in line]
        assert unpinned == []

    def test_lists_something(self):
        """Guard on the guard: the assertions above all pass on an empty file."""
        assert len(requirement_lines(PRODUCTION)) >= 8


class TestDeployPathDependencies:
    """Anything the release command imports has to be here, not in dev."""

    def test_includes_faker_because_seed_runs_on_deploy(self):
        assert "faker" in PRODUCTION.read_text(encoding="utf-8").lower()

    def test_includes_the_wsgi_server(self):
        assert "gunicorn" in PRODUCTION.read_text(encoding="utf-8").lower()

    def test_includes_the_postgres_driver(self):
        assert "psycopg" in PRODUCTION.read_text(encoding="utf-8").lower()

    def test_includes_the_static_file_server(self):
        assert "whitenoise" in PRODUCTION.read_text(encoding="utf-8").lower()


class TestDevelopmentManifest:
    def test_builds_on_production_rather_than_restating_it(self):
        """One production list, so the two cannot drift apart."""
        assert "-r ../requirements.txt" in DEVELOPMENT.read_text(encoding="utf-8")

    def test_adds_the_test_runner(self):
        assert "pytest" in DEVELOPMENT.read_text(encoding="utf-8").lower()

    def test_does_not_repeat_production_dependencies(self):
        production_names = {
            line.split("==")[0].split("[")[0].lower()
            for line in requirement_lines(PRODUCTION)
        }
        development_names = {
            line.split("==")[0].split("[")[0].lower()
            for line in requirement_lines(DEVELOPMENT)
        }
        assert production_names & development_names == set()
