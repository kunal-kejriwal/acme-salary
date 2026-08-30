"""Measure list-endpoint performance at full seed size.

The Incubyte team named server-side performance across 10,000 records as a
grading axis (REQUIREMENTS.md section 3), so the numbers in
docs/DECISIONS.md are measured rather than claimed. This script is what
produces them.

    python scripts/benchmark.py [--count 10000] [--repeat 20]

It seeds a real database, then times the employee list endpoint through the
full Django stack -- URL routing, filter backends, serializer, pagination --
not a bare queryset. Query counts come from the same requests.

The throwaway superuser exists because the API denies anonymous access. It is
created here, never by the seed command, which creates employees and FX rates
only. Its session and user lookups are counted in the query numbers below on
purpose: since Phase 6b every real request carries that cost, so excluding it
would flatter the figures.
"""

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from apps.core.seeding import seed_employees  # noqa: E402
from apps.employees.models import Employee  # noqa: E402

LIST_URL = "/api/v1/employees/"

#: (label, url, query params)
SCENARIOS = [
    ("List, first page", LIST_URL, {}),
    ("Filtered by country", LIST_URL, {"country": "IN"}),
    (
        "Filtered by department + title",
        LIST_URL,
        {"department": "Engineering", "job_title": "Senior Engineer"},
    ),
    (
        "Salary range (USD)",
        LIST_URL,
        {"salary_usd_min": "40000", "salary_usd_max": "90000"},
    ),
    ("Free-text search", LIST_URL, {"search": "an"}),
    ("Ordered by salary desc", LIST_URL, {"ordering": "-salary_usd"}),
    (
        "Filter + search + order",
        LIST_URL,
        {"department": "Engineering", "search": "a", "ordering": "-salary_usd"},
    ),
    ("Deep page (page 200)", LIST_URL, {"page": "200"}),
    ("Analytics: summary", "/api/v1/analytics/summary/", {}),
    ("Analytics: by country", "/api/v1/analytics/by-country/", {}),
    ("Analytics: by department", "/api/v1/analytics/by-department/", {}),
    ("Analytics: by title", "/api/v1/analytics/by-title/", {}),
]


def timed(client, url, params, repeat):
    """Median and p95 wall time in milliseconds, plus the query count."""
    client.get(url, params)  # warm caches and connection

    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        response = client.get(url, params)
        samples.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200, (url, params, response.status_code)

    with CaptureQueriesContext(connection) as captured:
        client.get(url, params)
    queries = len(captured)

    samples.sort()
    p95 = samples[min(int(len(samples) * 0.95), len(samples) - 1)]
    return statistics.median(samples), p95, queries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Benchmark against the data already present.",
    )
    args = parser.parse_args()

    if not args.skip_seed:
        start = time.perf_counter()
        with CaptureQueriesContext(connection) as captured:
            created = seed_employees(args.count, flush=True)
        seed_seconds = time.perf_counter() - start
        print(
            f"Seed: {created:,} employees in {seed_seconds:.2f}s "
            f"({len(captured)} queries, {created / seed_seconds:,.0f} rows/s)"
        )
        reset_queries()

    total = Employee.objects.count()
    print(f"Rows in database: {total:,}")
    print(f"Backend: {connection.vendor}")
    print()

    # Django's test Client sends Host: testserver.
    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="benchmark", defaults={"is_staff": True, "is_superuser": True}
    )
    client = Client()
    client.force_login(user)

    print(f"{'Scenario':<34} {'median':>10} {'p95':>10} {'queries':>8}")
    print("-" * 66)
    for label, url, params in SCENARIOS:
        median, p95, queries = timed(client, url, params, args.repeat)
        print(f"{label:<34} {median:>8.1f}ms {p95:>8.1f}ms {queries:>8}")

    user.delete()


if __name__ == "__main__":
    main()
