# CLAUDE.md — Project Instructions

You are building ACME Salary Management per `docs/ARCHITECTURE.md` and `docs/REQUIREMENTS.md`. Read both before any task. These rules apply to every prompt in this project:

## Non-negotiables
1. **TDD, strictly.** For every unit of behavior: write a failing test first, run it and show it fail, implement the minimum to pass, refactor. Never write implementation before its test exists.
2. **Commit discipline.** Small, incremental commits after each red-green-refactor cycle. Message format: imperative mood, behavior-focused — e.g. `test: add failing test for salary range filter`, `feat: implement salary range filter`, `refactor: extract filter builder`. Never bundle unrelated changes. Commit after EVERY green state, do not batch.
3. **Tests must be fast and deterministic.** pytest-django, SQLite test DB, Faker(seed=42), no network calls, no sleeps, no time-dependent assertions (freeze time where needed). Full suite must stay under 10 seconds.
4. **Money is Decimal.** Never float for salary or FX math.
5. **Thin views, fat services.** DRF views handle HTTP only; all business logic in `services.py` per app, tested directly.
6. **Idiomatic Django.** bulk_create(batch_size=1000), F() expressions, ORM aggregates/annotations over raw SQL, select_related/only where list views need it, choices for enums, django-filter for filtering.

## Stack (fixed — do not substitute)
- Python 3.12, Django 5, DRF, django-filter, drf-spectacular, django-cors-headers
- PostgreSQL in dev/prod (docker-compose), SQLite for tests
- pytest + pytest-django, Faker
- Frontend: React 18 + Vite + TypeScript + Ant Design + @ant-design/plots, Vitest + Testing Library
- Layout: `config/` settings package (base/dev/prod), apps under `apps/` (core, employees, imports, analytics), tests colocated per app

## Working style
- Work ONLY on the phase given in the current prompt. Do not scaffold ahead.
- If a decision isn't covered by the docs, state the assumption in the commit body and proceed — don't ask.
- After each phase: run the full test suite, show the output, list commits made.
- Update `docs/DECISIONS.md` with a dated entry whenever you make a non-obvious trade-off.
