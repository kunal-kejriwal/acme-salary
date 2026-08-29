# BUILD_PROMPTS.md — Claude Code phase prompts

Run these one at a time in Claude Code, in order. Review the diff and test output after each phase before starting the next. This file is committed as part of `AI_USAGE.md` evidence.

---

## Phase 0 — Scaffold
```
Read CLAUDE.md, docs/ARCHITECTURE.md and docs/REQUIREMENTS.md fully.

Scaffold the project: Django 5 project with config/ settings package (base/dev/prod),
apps/core, apps/employees, apps/imports, apps/analytics; DRF + django-filter +
drf-spectacular + django-cors-headers wired; pytest-django configured with SQLite
test settings; docker-compose.yml with Postgres and the API; Vite React TS app in
frontend/ with Ant Design installed; README with run instructions.

Verify: `pytest` runs (zero tests, exit 0), `python manage.py check` passes,
docker compose config validates. Commit in logical steps (scaffold, test config,
docker, frontend shell) — not one commit.
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
- Model with employee_code (unique), names, department, country, joined_on,
  salary_amount, currency, salary_usd, timestamps; indexes per §8
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
- Filters via django-filter: country, department, currency, salary_usd min/max
- Ordering: name, salary_usd, joined_on
- Free-text search across names + employee_code

Edge tests: empty page, out-of-range page, combined filters, filter+search+order
together. Assert query count on the list endpoint (assertNumQueries) to prove no
N+1.
```

## Phase 4 — Seed command
```
TDD `python manage.py seed --count 10000` in apps/core:
- Faker(seed=42); deterministic across runs (test: same checksum of first 100 rows)
- Countries weighted across the 8 currencies; ~10 departments
- Salaries log-normal per country so distributions look real
- bulk_create(batch_size=1000); test that runtime stays under a few seconds and
  exactly N rows land; idempotent via --flush flag

Then run it for real and commit a note of the timing in the commit body.
```

## Phase 5 — CSV import
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
vs against DB. These tests are the heart of the assessment — be thorough.
```

## Phase 6 — Analytics
```
TDD apps/analytics per docs/ARCHITECTURE.md §4, all in USD:
- /analytics/summary: headcount, total cost, avg, median
- /analytics/by-country and /by-department: headcount, avg, median, p10/p90
- /analytics/distribution: histogram buckets

Tests: small hand-computed fixture (e.g. 7 employees, known median/percentiles)
— assert exact values. Use ORM aggregation; portable percentile expression that
passes on SQLite (document in DECISIONS.md).
```

## Phase 7 — Export + auth
```
TDD:
- GET /api/v1/exports/employees.csv honoring the same filters as the list view
  (test: filtered export row count + header row)
- Session auth: single HR user, login/logout endpoints, everything else 401
  when unauthenticated (test both states). Create the HR user in seed.
```

## Phase 8 — Frontend
```
Build the React SPA with Ant Design against the running API:
- Login page
- Employees page: Table with server-side pagination/sort, filter bar
  (country/department/currency/salary range), search box, create/edit drawer
  with validation, delete confirm, salary history drawer
- Import page: Upload, result report card (counts), error table + errors.csv
  download link
- Dashboard: summary stat cards, by-country and by-department bar charts,
  salary distribution histogram (@ant-design/plots)

Vitest + Testing Library on: employees table renders server data, import flow
shows partial-failure report. Keep API access in a typed client module.
Commit per page, tests alongside.
```

## Phase 9 — Deploy prep
```
Production settings (env-driven DATABASE_URL, ALLOWED_HOSTS, CORS), Gunicorn,
Dockerfile, Railway config with release command (migrate + seed), Vercel config
for frontend/, README deploy section. Verify docker compose up works clean from
scratch. Final pass: run full suite, report timing, update DECISIONS.md.
```
