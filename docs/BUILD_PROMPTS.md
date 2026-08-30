# BUILD_PROMPTS.md — Claude Code phase prompts

Run these one at a time in Claude Code, in order. Review the diff and test output after each phase before starting the next. This file is committed as part of `AI_USAGE.md` evidence.

> **Scope confirmed by the Incubyte team** (see `REQUIREMENTS.md` §3). Authentication is out of scope entirely; CSV import is an optional stretch and now runs last, after deploy prep. Phases are renumbered accordingly.

---

## Phase 0 — Scaffold
```
Read CLAUDE.md, docs/ARCHITECTURE.md and docs/REQUIREMENTS.md fully.

Scaffold the project: Django 5 project with config/ settings package (base/dev/prod),
apps/core, apps/employees, apps/imports, apps/analytics; DRF + django-filter +
drf-spectacular + django-cors-headers wired; pytest-django configured with SQLite
test settings; Vite React TS app in frontend/ with Ant Design installed; README
with run instructions.

Verify: `pytest` runs, `python manage.py check` passes. Commit in logical steps
(scaffold, test config, frontend shell) — not one commit.
```

## Phase 1 — Core domain: currencies + FX
```
TDD the core money layer in apps/core:
- Currency choices (INR, USD, GBP, EUR, SGD, BRL, JPY, AUD)
- fx_rates static table/model seeded from a fixture in-repo
- to_usd(amount: Decimal, currency) service function

Tests first: conversion correctness against hand-computed values, Decimal
precision (no float drift), unknown-currency error. Then implement.
```

## Phase 2 — Employee model + CRUD API
```
TDD the Employee model and DRF CRUD per docs/ARCHITECTURE.md §3–4:
- Model with employee_code (unique), names, department, job_title, country,
  joined_on, salary_amount, currency, salary_usd, timestamps; indexes per §8
- salary_usd computed at write time via core.to_usd (service layer, not signals)
- SALARY_CHANGE audit row appended on every salary update, with tests proving it
- /api/v1/employees CRUD via DRF ViewSet, thin views calling services

Test order per behavior: model constraints → service logic → API contract
(APIClient). Include: create, update writes audit, delete, validation failures
(negative salary, bad currency).
```

## Phase 3 — List view: pagination, filtering, search
```
TDD server-side list behavior on GET /api/v1/employees:
- Page-number pagination (default 25)
- Filters via django-filter: country, department, job_title, currency,
  salary_usd min/max
- Ordering: name, salary_usd, joined_on
- Free-text search across names + employee_code

Edge tests: empty page, out-of-range page, combined filters, filter+search+order
together. Assert query count on the list endpoint (assertNumQueries) to prove no
N+1.
```

## Phase 4 — Seed command
```
TDD `python manage.py seed --count 10000` in apps/core:
- Deterministic given a seed. Test the PROPERTY, not a stored checksum: run
  the seed twice (--flush between) and assert identical rows. A hardcoded
  checksum breaks on any Faker upgrade, punishing a dependency bump rather
  than catching a determinism regression. Pin Faker in requirements anyway.
  Add the converse test: a different seed must produce different data.
- Countries weighted across the 8 currencies; ~10 departments; a realistic set
  of job titles per department
- Salaries realistic IN LOCAL CURRENCY, driven by (country, job title): each
  pair gets a local base with log-normal spread, so JPY salaries are in
  millions, INR in lakhs, USD in tens of thousands. One global range would
  produce nonsense and make the USD normalisation pointless. Title drives the
  multiplier so /analytics/by-title shows a seniority gradient.
- Seed must guarantee FX rates exist before converting — load the fixture
  first, or row one hits MissingRateError on a fresh database. Test that
  seeding a virgin DB succeeds.
- Creates employees and FX rates only. No HR user: auth is out of scope
  (REQUIREMENTS.md §7).
- bulk_create(batch_size=1000); assert query count rather than wall time
  (wall-clock assertions are flaky on CI); exactly N rows land; --flush to
  re-seed.

This is the confirmed way the 10,000 records are populated (REQUIREMENTS.md §3),
so it carries the load CSV import would otherwise have carried.

Then run it for real at 10,000 and record measured timings for the seed and
the list endpoint in DECISIONS.md — Sandli named server-side performance at
10k as a grading axis, so it needs evidence rather than a claim.
```

## Phase 5 — Analytics
```
TDD apps/analytics per docs/ARCHITECTURE.md §4, all in USD:
- /analytics/summary: headcount, total cost, avg, median
- /analytics/by-country, /by-department and /by-title: headcount, avg, median,
  p10/p90
- /analytics/distribution: histogram buckets

Tests: small hand-computed fixture (e.g. 7 employees, known median/percentiles)
— assert exact values. Use ORM aggregation; portable percentile expression that
passes on SQLite (document in DECISIONS.md).
```

## Phase 6 — CSV export
```
TDD:
- GET /api/v1/exports/employees.csv honoring the same filters as the list view
  (test: filtered export row count + header row, including job_title)

No auth work: authentication is out of scope per team guidance
(REQUIREMENTS.md §7).
```

## Phase 7 — Frontend
```
Build the React SPA with Ant Design against the running API:
- Employees page: Table with server-side pagination/sort, filter bar
  (country/department/job title/currency/salary range), search box, create/edit
  drawer with validation, delete confirm, salary history drawer
- Dashboard: summary stat cards, by-country, by-department and by-title bar
  charts, salary distribution histogram (@ant-design/plots)

No login page — the app is internal and the user is already authorized.

Vitest + Testing Library on: employees table renders server data, filter bar
drives server-side queries. Keep API access in a typed client module.
Commit per page, tests alongside.
```

## Phase 8 — Deploy prep
```
Production settings (env-driven DATABASE_URL, ALLOWED_HOSTS, CORS), Gunicorn,
Railway config with release command (migrate + seed), Vercel config for
frontend/, README deploy section. Final pass: run full suite, report timing,
capture query-count and timing evidence for the list and analytics endpoints at
10,000 records (REQUIREMENTS.md §8), update DECISIONS.md.
```

---

## Phase 9 — CSV import (stretch)

**Build only if every core phase above is complete and documented.** The Incubyte team confirmed bulk CSV import with row-by-row validation is not expected (`REQUIREMENTS.md` §6). Nothing in the core scope depends on this.

```
TDD the import pipeline per docs/ARCHITECTURE.md §5, in apps/imports:
- Import + ImportRowError models
- POST /api/v1/imports: multipart CSV; header validation fails fast with 400
- Stream-parse; per-row validation (types, currency, non-negative salary, date
  format, duplicate employee_code); collect errors with row numbers
- bulk_create(batch_size=1000) for valid rows; partial-import policy
- Response: full report (counts + errors); GET /imports/{id}; GET
  /imports/{id}/errors.csv download; sha256 checksum stored

Test fixtures: clean file, file with mixed valid/invalid rows (assert exact
counts and error rows), wrong header, empty file, duplicate codes within file
vs against DB.
```
