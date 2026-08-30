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

---

## 2026-08-29 — Phase 1, core money layer

### FX rates stored as `usd_per_unit`, not units-per-USD

**Decision.** `FxRate.usd_per_unit` reads as "1 unit of this currency is worth
N USD". Conversion is `amount * rate`.

**Why.** The alternative direction forces a division, which introduces a
repeating decimal for most rates and a rounding decision on every conversion.
Multiplication keeps the arithmetic exact until the single, deliberate
quantize at the end.

**Cost.** The stored numbers are less familiar to read for weak currencies
(INR is `0.012`, not `83.3`). Mitigated by `__str__` and the admin listing.

### `decimal_places=8` on the rate

**Decision.** `DecimalField(max_digits=18, decimal_places=8)`.

**Why.** JPY sits near 0.0064 USD. Two or four decimal places would round the
rate itself to zero or to a materially wrong value before any conversion
happened.

**Cost.** None meaningful; the column is small either way.

### Rounding is half-up, not Decimal's default half-even

**Decision.** `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.

**Why.** Decimal's default context uses `ROUND_HALF_EVEN` (banker's rounding),
which makes the result depend on the parity of the preceding digit — 0.005
rounds to 0.00 but 0.015 rounds to 0.02. That is defensible statistically and
surprising on a payslip. Half-up is the convention people expect from salary
figures.

**Cost.** A very slight upward bias across a large population. At ACME's scale
the total distortion is under a cent per employee, against the benefit of
figures that reconcile the way an HR manager expects.

**Verified.** The test asserting `0.005 -> 0.01` was checked to fail under
half-even, so it is not a vacuous assertion.

### `to_usd` rejects floats at the boundary

**Decision.** Non-`Decimal`, non-`int` input raises `TypeError`. `bool` is
rejected too, despite subclassing `int`.

**Why.** CLAUDE.md forbids float money. Silently coercing a float would honour
the letter of that and miss the point: the precision is already lost by the
time the value arrives. Raising makes the mistake visible at the call site.

**Cost.** Callers holding a float must convert explicitly, via
`Decimal(str(value))`. That is the correct ceremony, not an inconvenience.

**Verified.** The drift test (`2.675 USD -> 2.68`) was checked to produce 2.67
under a float implementation, so it discriminates.

### Two error types, not one

**Decision.** `UnknownCurrencyError` and `MissingRateError`, both subclassing
`FxError(ValueError)`.

**Why.** They are different failures with different fixes. An unsupported code
is bad input data and belongs in a per-row import error the HR manager sees. A
supported currency with no seeded rate is a deployment fault — the fixture was
never loaded — and no amount of data cleaning fixes it. One error type would
send whoever reads it looking in the wrong place.

**Cost.** One extra class. The base `FxError` means callers who genuinely do
not care can still catch a single type.

### Currency codes are matched case-sensitively

**Decision.** `to_usd(amount, "inr")` raises `UnknownCurrencyError`.

**Why.** Normalising case is a parsing concern, and the layer that sees raw
user input is the CSV importer. Doing it here would silently accept malformed
data everywhere else too, and hide the fact that a file needs cleaning.

**Cost.** The import layer must upper-case codes before calling `to_usd`.
Tracked for Phase 5.

### Known gap: `to_usd` queries per call

**Decision.** `get_rate` does one `FxRate` query per conversion. Left as is.

**Why.** The Phase 1 brief fixes the signature at `to_usd(amount, currency)`,
and a module-level cache would need invalidation logic that is easy to get
wrong in tests.

**Cost.** Real. Importing 10,000 rows through this function would issue 10,000
queries, against ARCHITECTURE.md §5's batched design. Phase 5 needs a
`rate_map()` helper that loads all eight rates once and a bulk-friendly call
path. Flagged here so it is not discovered late.

---

## 2026-08-29 — Phase 2, employee model and CRUD API

### `SalaryChange` records currency on both sides — a deviation from the §3 ERD

**Decision.** The ERD in ARCHITECTURE.md §3 gives `SALARY_CHANGE` a single
`currency` column. The model has `old_currency` and `new_currency` instead.

**Why.** With one column, a move from 100,000 INR to 2,000 USD — a substantial
raise — stores `old_amount=100000, new_amount=2000, currency=USD` and reads
back as a 98% pay cut. An audit trail that can invert the direction of a pay
change is worse than a diagram that has drifted, and this is precisely the
table HR and compliance would reach for.

**Cost.** ARCHITECTURE.md §3 is now out of date on this entity. Two extra
columns, both cheap.

**Alternative rejected.** Forbidding currency changes on the update path would
have preserved the ERD, but relocation between countries is an ordinary HR
event and the product should not refuse it to protect a diagram.

### The audit write lives in the service, not a signal or `save()` override

**Decision.** `update_employee` writes the `SalaryChange` row explicitly. There
is no `post_save` receiver and no overridden `save()`.

**Why.** A model hook is the obvious-looking place and the wrong one. It fires
on fixture loads and data migrations, producing audit rows nobody asked for. It
does *not* fire on `bulk_create` or `QuerySet.update()`, so Phase 5's batched
import would silently write no history at all. And it hides the write from
anyone reading the call site, which is the opposite of what an audit trail is
for.

**Cost.** Any future write path must remember to go through the service. The
model makes forgetting expensive: `salary_usd` is `NOT NULL` with no default,
so a bypassing write fails rather than silently storing a wrong figure.

**Guarded by tests.** `TestAuditIsNotHiddenInTheModel` asserts that a direct
`employee.save()` and a `QuerySet.update()` both write *no* audit row. If
someone relocates the logic into a hook, those tests fail — which is the
intent.

### Non-negative salary is a `CheckConstraint`, not only a validator

**Decision.** Both, but the database constraint is the one that matters.

**Why.** `MinValueValidator` only runs on `full_clean()`, which
`bulk_create` skips entirely. Phase 5 inserts thousands of rows that way.

**Cost.** None. Zero is allowed — unpaid interns and leave-of-absence records
are real.

### Case normalisation at the serializer, strictness in `core.to_usd`

**Decision.** `to_usd("inr")` still raises. `POST /employees` with
`{"currency": "inr"}` succeeds and stores `INR`.

**Why.** The two layers have different jobs. A currency code arriving at
`to_usd` from an internal caller is a programming or data-pipeline fault and
should surface. A code arriving over HTTP is user input, and rejecting it on
case alone is hostile. Forgiving at the boundary, exact underneath.

**Implementation note.** The normalisation runs in `to_internal_value`, not
`validate_currency`. DRF's `ChoiceField` rejects `"eur"` during field
validation, before any `validate_<field>` hook is reached — a `validate_currency`
implementation would look correct and never run.

**Cost.** `to_internal_value` is a slightly heavier hook than a field
validator, and it copies the incoming data. Country gets the same treatment for
consistency.

### `salary_usd` is read-only over the API

**Decision.** Clients cannot set it on create or update.

**Why.** It is derived. Accepting it would let a caller store a normalised
figure that contradicts the salary it is supposed to represent, and every
analytics aggregate reads the derived column.

**Cost.** None. A test asserts a client-supplied value is ignored rather than
honoured, so the field cannot quietly become writable.

### `SimpleRouter` rather than `DefaultRouter`

**Decision.** `SimpleRouter` in each app's `urls.py`.

**Why.** Employees, imports and analytics are all included at the `/api/v1`
prefix. `DefaultRouter` registers an API-root view at `""`, so three of them
would collide and only the first would resolve.

**Cost.** No browsable API index at `/api/v1/`. `/api/docs/` already serves
that purpose better.

---

## 2026-08-30 — Scope confirmed by the Incubyte team

A clarification email to the Incubyte team (Sandli Srivastava) came back with
direct answers on five open questions. Scope is adjusted mid-build to match.
`REQUIREMENTS.md` §3 records the answers; this entry records what they cost.

### What changed

| Guidance | Effect |
|---|---|
| Currency model confirmed as proposed | No change. Phase 1 already ships local-currency storage with a seeded FX table and USD normalisation. |
| Schema confirmed: ID, Name, Department, **Job Title**, Country, Base Salary, Currency, Joined Date | `job_title` added to the model, indexes, list filters, seed and analytics groupings. |
| Bulk CSV import **not expected**; a Faker seed script is sufficient | F3 demoted from core to stretch; the import phase moves last. |
| Authentication, self-service and RBAC **explicitly out** | F7 (login) deleted; auth moved to Deliberately Out; the old "Export + auth" phase keeps only the export. |
| Graded on architecture, server-side performance at 10k, documentation — not speed | Success criteria rewritten around deterministic seeding and committed performance evidence. |

### Cost of the adjustment

Close to zero, but not literally zero, and worth being precise about since the
guidance arrived *after* Phase 2 had already shipped:

- **Auth removal: no cost.** No user model, login endpoint or permission
  matrix was ever built. DRF's `IsAuthenticated` default and the session-auth
  config in `settings/base.py` stay as a sane posture, and the API tests keep
  a small check that anonymous access is refused — but no auth *feature* was
  written and none now needs unwinding.
- **Import demotion: no cost.** `apps/imports` is an empty scaffold. Nothing
  in the core scope imports from it.
- **`job_title`: real but bounded rework.** Phase 2 landed without it, so the
  column, its index, a migration, the serializer field and the affected tests
  were outstanding. One migration on a table with no production data.

  **Closed the same day.** `job_title` shipped as migration
  `0002_employee_job_title` (a one-off default with `preserve_default=False`,
  so nothing written after it may omit a title), with the index from
  ARCHITECTURE.md §8, the serializer field, `filterset_fields` and
  `ordering_fields` entries, admin column, and tests covering the field being
  required, indexed, returned, filterable and orderable. The docs and the
  code describe the same model again. Suite: 140 passed.

The larger win is what the guidance prevented: Phases 5 through 8 had not
started, so the import pipeline, the login page and the RBAC groundwork were
never written and then thrown away.

### Grading emphasis and where the repo answers it

The team named three priorities. Each maps to something concrete:

| Priority | Evidence in the repo |
|---|---|
| **Clean code architecture** | Thin views, business logic in per-app `services.py` tested directly; `to_usd` isolated from HTTP; the audit write deliberately in the service rather than a signal, with tests asserting no hidden write path (`TestAuditIsNotHiddenInTheModel`). |
| **Server-side performance across 10,000 records** | Server-side pagination, filtering and aggregation throughout; indexes per ARCHITECTURE.md §8; `django_assert_num_queries` already pinning the employee list view; Phase 8 commits query-count and timing evidence at full seed size rather than asserting it. |
| **Strong documentation** | `REQUIREMENTS.md` for scope, `ARCHITECTURE.md` for design and its rationale, this log for trade-offs, `AI_USAGE.md` for workflow, and commit bodies that state the reasoning and the assumptions behind each step. |

### Note on the ERD

`ARCHITECTURE.md` §3 now carries `job_title`. It remains out of date in one
other place, recorded separately above: `SALARY_CHANGE` stores currency on both
sides, which the diagram does not show.

---

## 2026-08-30 — Phase 3, server-side list view

### Salary range filters compare `salary_usd`, never `salary_amount`

**Decision.** `salary_usd_min` and `salary_usd_max` filter the normalised USD
column. The local-currency column is not filterable by range at all.

**Why.** This is the one filter where the obvious column returns answers that
look fine and mean nothing. `salary_amount` is a bare number whose unit varies
per row, so a range over it compares INR against GBP against JPY. Concretely,
a "salary between 900,000 and 1,100,000" query would match both a 1,000,000
INR salary (~12,000 USD) and a 1,000,000 GBP salary (~1,270,000 USD) — two
people whose actual pay differs by a factor of a hundred — while excluding a
250,000 USD salary that sits between them. The HR manager asking that question
is asking about *pay*, not about digits.

This is the write-time normalisation from ARCHITECTURE.md §3 earning its keep.
Because `salary_usd` is materialised, a cross-currency range query is a plain
indexed comparison with no join and no conversion at read time.

**Cost.** The USD figures carry the FX staleness already documented for the
static rate table. A range query is therefore accurate as of the seeded rates,
not as of today's market — acceptable, and the alternative is wrong rather
than merely stale.

**Naming.** The parameters say `usd` out loud (`salary_usd_min`, not
`salary_min`) so a caller cannot mistake which currency the bound is in.

**Verified.** Repointing the filters at `salary_amount` fails 5 of the 7 tests
in `TestSalaryRangeFiltersOnUsd`, including the case where three employees
share an identical `salary_amount` and only their USD values separate them.

### Every ordering is total, via an `id` tiebreaker

**Decision.** `StableOrderingFilter` (`apps/core/filters.py`) appends `id` to
any client-supplied ordering, and `Employee.Meta.ordering` ends in `id` for the
default path. Registered as the project-wide default filter backend.

**Why.** Every column the UI sorts by — surname, salary, joined date, job title
— is non-unique. Ordering by one alone is a *partial* order, so tied rows come
back in whatever sequence the database produces, and that sequence is not
guaranteed to be the same between two queries. Under pagination this is a
correctness bug rather than a cosmetic one: when a run of tied rows straddles a
page boundary, a row can appear on both page 1 and page 2, or on neither. It is
invisible in small datasets and shows up exactly where it matters — 10,000
rows, with ties on salary and department.

It also removes any path that could raise Django's
`UnorderedObjectListWarning`.

**Cost.** One extra sort key, resolved only among rows that already tied. The
`(last_name, first_name)` index still serves the leading columns.

**Verified.** Removing both mechanisms fails the three id-order assertions.

**Honest limit.** The other three tests in that class — repeated-request
stability, non-overlapping pages, and the warning guard — pass either way on
SQLite, whose scan order happens to be stable in practice. They document the
intent and would catch a regression on Postgres, which genuinely can reorder;
the id-order assertions are the ones carrying the weight.

### The query-count assertion pins a contract, not an N+1

**Decision.** `django_assert_num_queries(2)` on the list endpoint — one COUNT
for pagination, one SELECT for the page — with a docstring saying why.

**Why.** `Employee` has no forward relations, so an N+1 cannot occur on this
endpoint today. Asserted without explanation, the test would read as cargo
cult. Its value is forward-looking: it fixes the cost of the list view, so the
moment a relation reaches this serializer — salary history, a department FK,
anything with a `select_related` it forgot — the extra per-row query fails a
test in milliseconds instead of surfacing as a slow page at 10,000 rows.

**Cost.** The number must be updated deliberately when the endpoint legitimately
gains a query. That is the point: the update is a decision someone makes, not a
regression that slips past.

### Search covers names and employee code only

**Decision.** `search_fields = ["first_name", "last_name", "employee_code"]`.

**Why.** Department, job title, country and currency all have exact filters.
Folding them into free-text search would make a query for "Finance" match both
a surname and a department, so the result set stops answering a single
question.

**Cost.** A user searching for a department in the search box gets nothing.
The filter bar is the right affordance for that, and Phase 7 builds it.

### Pagination response shape stays DRF's default

**Decision.** `{count, next, previous, results}`, unmodified.

**Why.** Ant Design's `Table` maps onto it directly — `count` to `total`,
`results` to `dataSource`. A custom envelope would buy nothing and cost
translation code in Phase 7.

**Not added.** A `page_size` query parameter. The default of 25 covers the
current requirement; if Phase 7 wants a page-size selector it is a one-line
`page_size_query_param` on a pagination class, and the response shape does not
change.
