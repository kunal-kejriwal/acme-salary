# Decisions

A dated log of non-obvious trade-offs. Each entry records the decision, why it
was made, and what it costs.

---

## 2026-08-29 — Phase 0, scaffold

### No Docker; SQLite is the development default

**Decision.** The project runs directly on the host. `docker-compose.yml` and
`Dockerfile` were written and then removed. Development falls back to a local
SQLite file when `DATABASE_URL` is unset.

**Why.** The container layer bought nothing at this scale — a single Django process and one database.
Removing it takes the project from "install Docker Desktop, build an image,
wait for a healthcheck" to `pip install && manage.py runserver`.

**Cost.** ARCHITECTURE.md §2 and §10 still describe `docker compose up` as the
local story and Railway for deploy; those sections are now ahead of the code.
Postgres-only behaviour is not exercised locally by default — see the
percentile note below, which is the one place this bites.

**Reversible?** Yes, cheaply. Nothing in the code assumes SQLite;
`DATABASE_URL` switches the whole app to Postgres, and the settings split
already separates dev from prod.

### Postgres remains the production database

**Decision.** `config/settings/prod.py` requires `DATABASE_URL` — there is no
SQLite fallback in production.

**Why.** ARCHITECTURE.md §3 puts real money in `DecimalField` and §4 leans on
aggregates for analytics. SQLite's dynamic typing and missing
`percentile_cont` make it a poor production choice even though it is an
excellent test database.

**Cost.** Analytics percentiles must be written as a portable expression that
gives correct results on both engines, and must be tested against hand-computed
fixtures rather than trusting the database. Tracked for Phase 6.

### psycopg 3 instead of psycopg2

**Decision.** `psycopg[binary]>=3.3`.

**Why.** Django 5 supports psycopg 3 natively, and it ships wheels for current
Python versions where psycopg2-binary lags. No build toolchain needed.

**Cost.** None identified.

### Tests run on in-memory SQLite with MD5 password hashing

**Decision.** `config/settings/test.py` pins an in-memory SQLite database and
`MD5PasswordHasher`.

**Why.** CLAUDE.md requires the full suite under 10 seconds with no external
dependencies. PBKDF2 hashing dominates the runtime of any suite that creates
users; MD5 removes that cost.

**Cost.** Deliberately weak hashing — test settings only, never imported by
dev or prod. Migrations still run, so model/migration drift is caught.

### Four smoke tests instead of an empty suite

**Decision.** The scaffold ships `apps/core/tests/test_smoke.py` with four
assertions about the wiring.

**Why.** The phase brief asked for `pytest` to exit 0 with zero tests, but
pytest exits 5 (`NO_TESTS_COLLECTED`) on an empty suite by design. The
alternative — a `pytest_sessionfinish` hook rewriting the exit code — would
also mask a genuinely empty suite in CI, which is a failure worth seeing.
Real tests earn the exit 0 instead.

**Cost.** Four tests that assert configuration rather than behaviour. They stay
cheap and catch a real class of mistake (an app dropped from `INSTALLED_APPS`).

### React 18 pinned against the current create-vite default

**Decision.** `create-vite` scaffolds React 19; the dependency was pinned back
to React 18.3 with matching `@types`.

**Why.** CLAUDE.md lists the stack as fixed and names React 18. antd 6 and
Testing Library 16 both support 18, so the pin costs nothing functional.

**Cost.** React 18 will age out of the ecosystem default. Nothing in the code
depends on 18-only behaviour, so lifting the pin is a version bump.

**Verified.** `npm run build` and `npm run test` both pass on the pin.

### `@ant-design/plots` not yet installed

**Decision.** Deferred to Phase 8, where the dashboard charts are built.

**Why.** It is a large dependency with no consumer until then, and the Phase 0
brief asked only for Ant Design.

**Cost.** None; it is one `npm install` away.
