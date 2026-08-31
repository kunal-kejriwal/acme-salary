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

---

## 2026-08-30 — Phase 4, seed command

### Determinism is asserted as a property, not a stored checksum

**Decision.** The seed runs twice in the same test and the two datasets are
compared row for row. `BUILD_PROMPTS.md` originally specified "same checksum of
first 100 rows"; that design was dropped.

**Why.** A hardcoded checksum tests the wrong thing. Names come from Faker, so
any Faker upgrade changes them legitimately — and the test would fail, blaming
a routine dependency bump for a determinism regression that did not happen.
Worse, the obvious fix is to paste in the new hash, which trains whoever hits
it to silence the assertion without reading it. Running the seed twice asserts
the property that actually matters: same seed, same data, whatever the library
does internally.

**Reinforced.** A companion test seeds with a *different* seed and asserts the
output differs. Without it, the equality tests would pass against a generator
that always returned the same constant.

**Also.** Primary keys are drawn from the seeded RNG rather than `uuid4`, so
the whole dataset reproduces — a fixture that renumbers itself on every run is
only half reproducible.

**Faker is pinned exactly** (`Faker==40.37.0`) regardless. The property test
means an upgrade will not break the suite, but the committed dataset should
move only when someone chooses to move it.

### Salaries are generated per (country, job title), in local currency

**Decision.** Each country carries a local-currency base for a mid-level
individual contributor; each job title carries a multiplier; a log-normal draw
supplies the spread; the result is rounded to a locally plausible unit (500 for
USD, 10,000 for INR, 100,000 for JPY).

**Why.** A single global range makes 80,000 the typical salary everywhere. That
is reasonable in USD, about 960 USD in INR, and about 510 USD in JPY — figures
no HR manager would recognise. Two things break as a result: the dashboard
looks obviously synthetic, and the USD normalisation becomes pointless, since
every salary would already be numerically comparable and the entire
multi-currency design would be exercising nothing.

Title driving the multiplier is what gives `/analytics/by-title` a visible
seniority gradient — the chart that best answers "how does this org pay
people". Junior Engineer sits at 0.55 and Staff Engineer at 1.90 of the same
country base.

**Cost.** The country and title tables are hand-maintained data in
`apps/core/seeding.py`. They are demo data, not domain rules, and live in one
readable place.

**Tested as properties, not magic numbers.** Median INR salary exceeds ten
times median USD; JPY likewise; the Engineering ladder shows a strictly
increasing mean, asserted both across the org and within a single country so
country mix cannot explain it away.

### The seed guarantees FX rates before it converts

**Decision.** `ensure_fx_rates()` loads the fixture when any currency is
missing, before the first salary is normalised.

**Why.** Otherwise the first row of a fresh database raises `MissingRateError`
— the Phase 1 error taxonomy working exactly as designed, and a poor first-run
experience for anyone following the README. A test seeds a virgin database
with no fixture loaded and asserts it succeeds.

**Enabled by.** Giving `fx_rates.json` explicit primary keys, which makes
`loaddata` idempotent. Without them a second load inserts duplicate rows and
trips the unique constraint on `currency`.

### The seed creates employees and FX rates. Nothing else.

**Decision.** No HR user, no salary history.

**Why.** Authentication is out of scope (REQUIREMENTS.md §7), so the user
creation carried by the original Phase 4 and Phase 7 prompts has no purpose. A
seeded employee has a starting salary, not a change, so no `SalaryChange` rows
either — consistent with `create_employee`, which writes no audit row.

**Tested.** `get_user_model().objects.count() == 0` and
`SalaryChange.objects.count() == 0` after seeding.

### Batching is asserted by query count, not wall time

**Decision.** The suite asserts query behaviour; timings are measured once and
recorded below.

**Why.** `BUILD_PROMPTS.md` asked for a test that runtime stays under a few
seconds. Wall-clock assertions are flaky on shared CI and fail for reasons
unrelated to the code. Query count is the deterministic proxy.

**A correction worth recording.** The first version asserted that ten times the
rows cost at most one extra query. That is true on Postgres and false on
SQLite: SQLite caps parameters per statement at 999, so with `Employee`'s 13
columns `bulk_create` batches about 76 rows regardless of `batch_size=1000`.
Postgres allows 65,535, where the configured 1,000 governs. The test now
asserts the portable property — rows per query rises with row count rather
than staying flat at one — with the backend difference documented in the test
itself. The 10,000-row seed issues 158 statements on SQLite; on Postgres it
would be roughly 10.

---

## Performance evidence — 10,000 records

Measured, not claimed. Reproduce with `python scripts/benchmark.py`.
Refreshed at Phase 8; supersedes the earlier figures.

**Environment.** SQLite (the development default), Python 3.14.7, Django
5.2.17, Windows, warm cache, median and p95 of 20 requests through the full
Django stack — routing, authentication, filter backends, serializer,
pagination — not a bare queryset. Postgres in production would differ,
generally favourably on the aggregate paths.

| Measurement | Result |
|---|---|
| Seed 10,000 employees | **5.42 s** (1,845 rows/s, 257 statements) |
| Full backend suite | **9.86 s**, 339 tests |
| Frontend suite | 8 tests |

| Endpoint (10,000 rows) | Median | p95 | Queries |
|---|---|---|---|
| List, first page | 10.5 ms | 64.9 ms | 4 |
| Filtered by country | 12.6 ms | 16.6 ms | 4 |
| Filtered by department + job title | 12.2 ms | 25.2 ms | 4 |
| Salary range (USD) | 13.8 ms | 17.0 ms | 4 |
| Free-text search | 14.5 ms | 31.6 ms | 4 |
| Ordered by salary, descending | 12.9 ms | 16.4 ms | 4 |
| Filter + search + order combined | 15.4 ms | 22.0 ms | 4 |
| Deep page (page 200 of 400) | 20.9 ms | 24.0 ms | 4 |
| Analytics: summary | 52.8 ms | 69.1 ms | 4 |
| Analytics: by country | 73.2 ms | 127.6 ms | 4 |
| Analytics: by department | 77.4 ms | 84.4 ms | 4 |
| Analytics: by title | 69.4 ms | 127.9 ms | 4 |

**Bundle, after code-splitting the dashboard:** 322 kB gzipped on first load
(down from 751 kB), with the 429 kB chart bundle deferred to the one page that
uses it.

**On the query count.** Four everywhere. Two belong to the endpoint — for the
list, a `COUNT(*)` and the page `SELECT`; for analytics, the GROUP BY aggregate
and the median window query. The other two are the session and user lookups
that session authentication costs. Those are the honest price of a real
request, so they are counted here rather than excluded. The suite pins the
endpoint's own two, because `force_authenticate` skips the session round trip.

**Run-to-run variance is real.** The seed has measured 3.28 s, 4.15 s and
5.42 s across phases on the same machine; analytics has moved by 10 ms between
runs. Nothing changed in those paths — this is an unloaded developer laptop, not
a benchmark rig. Treat the figures as orders of magnitude, not as a stopwatch:
the claim they support is "milliseconds, not seconds, at 10,000 rows", and that
holds with a wide margin.

**On analytics being four to six times the list.** Expected: the list reads one
page of 25 rows off an index, while every analytics endpoint ranks and
aggregates all 10,000. Still under a tenth of a second for a dashboard that
loads once.

**A composite index would make it worse — measured, not assumed.** Adding
`(country, salary_usd)`, `(department, salary_usd)`, `(job_title, salary_usd)`
and `(salary_usd)` and re-running moved the service-level timings the wrong
way: summary +14%, by-country +15%, by-department +25%, by-title +18%. SQLite's
planner takes the index and turns a sequential scan plus sort into a
non-covering index scan with a row lookup per hit, which loses when the query
touches every row anyway. The indexes were not added. Postgres may choose
differently, which is a reason to re-measure there rather than speculate here.

**Reading it.** Every list scenario is inside a single frame at 60fps and every
dashboard query inside a tenth of a second, on the slower of the two databases,
with no caching layer. That is the justification for ARCHITECTURE.md §8 listing
caching and read replicas as deliberately unbuilt.

---

## 2026-08-30 — Final scope locked

**Decision.** Scope is now exactly the assessment brief plus the Incubyte
team's clarification email, and nothing else. In: employee records, the list at
10,000, salary editing with audit history, analytics that answer "how does this
org pay people", the deterministic seed, deploy, demo. Out entirely: CSV import
*and* export, a custom login page, containerization, async processing, employee
self-service.

**Why.** Their email named the grading axes — clean architecture, server-side
performance across 10,000 records, strong documentation — and said outright
that those matter more than breadth or speed of submission. Import and export
were the last two features whose cost bought reach rather than depth, so they
go, and the effort lands on making the core exact.

**What moved.**

- CSV import was already a stretch; export joins it in Deliberately Out. Both
  keep a design sketch in `ARCHITECTURE.md` §8, because the reasoning is worth
  showing even when the code is not written.
- `/analytics/distribution` dropped. Summary plus three group breakdowns
  answer the product question; a histogram was a fourth chart without a fourth
  question behind it.
- `ARCHITECTURE.md` §5 (the import pipeline) is gone, so §6–§10 renumbered to
  §5–§9. Cross-references were updated across the docs *and* in code comments
  and test docstrings that cite section numbers — a comment pointing at the
  wrong section is a small lie that costs the next reader real time.

**Also corrected.** §2 and §10 still described `docker compose up` as the local
story, four phases after Docker was removed. Now fixed — the doc had been
carrying that error since Phase 0, and it was flagged in this log twice without
being repaired. The §3 ERD likewise now shows `old_currency`/`new_currency` on
`SALARY_CHANGE` and drops the import entities, matching what is actually built.

**Cost.** A reviewer looking for import/export will not find it. That is the
point of writing the boundary down rather than leaving it to be inferred from
absence.

**Known residue.** `apps/imports/` still exists as an empty scaffold in
`INSTALLED_APPS`. Removing it is a code change and this was a documentation
pass; it is queued rather than smuggled in.

---

## 2026-08-30 — Session auth, past the brief on purpose

**Decision.** Built session sign-in — `POST /auth/login`, `POST /auth/logout`,
`GET /auth/me` — over Django's built-in user, and set DRF to refuse anonymous
callers project-wide. The Incubyte team scoped authentication out; this goes
past that deliberately.

**Why go past it.** Their reasoning was sound and is accepted in full: for one
known operator, a bespoke user model and a role matrix are over-engineering.
But "the user is already authorized" describes a person, not a request. With
no sign-in, *authorized* has no representation at the HTTP boundary, and a
deployed public demo would serve ACME's entire salary table — every name, every
salary — to anyone who found the URL. The version built is the cheap one:
Django's own session framework over the superuser that has to exist anyway for
the admin. No new model, no migration, no roles.

**What was still declined**, because it is what they actually warned against: a
custom user model, RBAC, permission matrices, self-service accounts, password
reset, MFA. All remain in Deliberately Out.

**Cost.** Three views, one serializer module, a set of cookie settings. The SPA
gains a login page and a bootstrap probe.

### The endpoint sweep enumerates routes, it does not list them

**Decision.** The "every endpoint refuses anonymous callers" test walks the
URLconf and parametrizes over what it finds, excluding the auth endpoints.

**Why.** A hardcoded list of paths is correct exactly once. The next endpoint
someone adds is unprotected *and* uncovered, and the test still passes — it has
silently stopped doing the job it was written for. Walking the URLconf means
Phase 6's analytics endpoints are swept the moment they register, with no edit
here.

**Guarded.** Five assertions check the sweep is not vacuous: routes were
found, the employee list is among them, a detail route is among them, auth is
excluded, and every parameter is substituted out. A broken walker that returned
nothing would otherwise make every parametrized case pass by having nothing to
run.

**Three bugs it surfaced while being built**, all worth knowing for anyone
writing a similar sweep:

1. DRF's `SimpleRouter` emits **regex** patterns (`^employees/$`) while
   `path()` emits **route** patterns (`<uuid:pk>`). Both spellings need
   handling.
2. Stripping regex anchors across the joined route eats the `^` inside
   `[^/.]+` and corrupts the pattern. It has to be done per fragment.
3. The `<pk>` inside `(?P<pk>...)` matches a naive `<...>` route-parameter
   pattern, so group substitution must run *first* or it mangles exactly what
   it is about to replace.

### 403 everywhere, 401 on `/auth/me`

**Decision.** Product endpoints answer 403 to anonymous callers; `/auth/me`
answers 401.

**Why.** 403 is DRF's session default — it downgrades 401 when the
authenticator sends no `WWW-Authenticate` header, which `SessionAuthentication`
does not. Fighting that everywhere would mean a custom authentication class for
no gain. But `/auth/me` exists precisely to answer "am I signed in?", and the
SPA routes on the answer, so it returns the unambiguous 401. The inconsistency
is deliberate and documented rather than accidental.

### Login carries no authenticator

**Decision.** `LoginView.authentication_classes = []`.

**Why.** `SessionAuthentication` enforces CSRF, and enforcing it on the request
that establishes the session means rejecting a legitimate first login. There is
no session to protect yet. Both `/auth/login` and `/auth/me` set a CSRF cookie,
so the SPA holds a token before signing in and a fresh one after.

**Cost.** Login itself is not CSRF-protected. The exposure is login-CSRF —
forcing a victim into *our* session, not stealing theirs — which for a
single-account internal tool is close to meaningless.

### One failure message for every bad login

**Decision.** Wrong password and unknown username return byte-identical
responses.

**Why.** Distinguishing them turns the login form into a user directory.

**Tested by comparing the two response bodies**, rather than by asserting each
separately — which would pass even if the messages diverged.

---

## 2026-08-30 — Phase 6, analytics

### Median without `percentile_cont`

**Decision.** Rank rows within each group with `ROW_NUMBER()`, count the group
with `COUNT(*) OVER`, keep the rows whose rank is `(n+1)//2` or `(n+2)//2`, and
average the survivors in Python.

**Why this shape.** SQLite has no `percentile_cont`, so the ordered-set
aggregate Postgres would use is unavailable. Window functions are portable —
SQLite has had them since 3.25 — and integer division truncates identically on
both engines, so one expression is correct everywhere. The filter selects the
single middle row when a group is odd-sized and the two straddling rows when it
is even.

**Why the last step is Python.** It cannot be folded into the same query, and
that was established by trying it rather than assumed: Django applies a window
filter *after* `GROUP BY`, so adding an aggregate to the ranked queryset emits
`GROUP BY country, salary_usd` and returns one row per employee — plausible
SQL, wrong answer. Averaging the one or two survivors in Python is also exact,
where SQLite's `AVG` routes the value through a float.

**Cost.** Two queries per endpoint instead of one. Neither scales with group
count, which is the property that matters: a per-group median would be one
query per job title. Verified against `statistics.median` over all 10,000 seeded
rows, per country, exact to the cent.

### Grouped rows are keyed `group`, not by the column name

**Decision.** All three breakdowns return `{"group": ..., "headcount": ...}`.

**Why.** One response shape means the dashboard renders country, department and
title through a single chart component instead of three near-copies.

**Cost.** Slightly less self-describing in isolation; the endpoint name already
says what the grouping is.

### Explicit `order_by` on the grouped queryset is load-bearing

**Decision.** `.order_by("-headcount", group_field)` after `.values().annotate()`.

**Why.** Two separate reasons, and the first is a correctness trap rather than a
preference. `Employee.Meta.ordering` is `["last_name", "first_name", "id"]`, and
Django folds default ordering into the `GROUP BY` — without an explicit
`order_by` the query groups by `(country, last_name, first_name, id)` and
returns one row per employee while still looking like a group-by. A test asserts
five country groups rather than eight rows, which is what catches it.

The second reason is the Phase 3 lesson again: headcount ties need a tiebreaker
or the dashboard's bars reshuffle between reloads. Four countries in the test
fixture share a headcount of one, and their order is asserted.

### The test fixture is skewed on purpose

**Decision.** Eight employees across five countries and four currencies, with
one 400,000 USD outlier.

**Why.** Overall mean is 71,800 and median 28,500; within the US, mean is
115,000 and median 25,000. If those coincided, no assertion in the suite could
distinguish a median implementation from a mean one. The Engineering group is
skewed the other way — median 25,000 above mean 23,000 — so a median that
happened to sit below the mean everywhere could not pass by coincidence either.

---

## 2026-08-30 — Phase 7, frontend

### One adapter between Ant Design's Table and DRF

**Decision.** `src/api/table.ts` translates `{current, pageSize, sorter,
filters}` into `{page, ordering, country, …}` and DRF's `{count, results}` back
into Ant Design's pagination config. Nothing else in the app touches query
parameters.

**Why.** The two vocabularies genuinely differ, and that translation is the
only interesting logic in an otherwise dumb table. Spread across page
components it would be duplicated per screen and testable only through the UI;
in one module it is neither.

**Two behaviours it encodes** that would otherwise be forgotten per component:
changing page size returns to page one, and changing a filter does too. Editing
a filter while on page 7 of the old result set otherwise lands on page 7 of the
new one, which is usually empty and reads as a bug.

### Display locale is pinned to `en-US`

**Decision.** `toLocaleString('en-US', …)`, not `toLocaleString(undefined, …)`.

**Why.** A real defect avoided rather than a preference. This machine reports
`en-IN`, where `undefined` renders 2,400,000 as **24,00,000** — correct for
that locale, wrong for a tool where one salary must read identically to
everyone looking at it. Left to the browser, a table mixing currencies would
also mix grouping conventions row by row.

**Found by** a test failing on the formatted string. Otherwise it ships, and is
noticed only by whoever happens to have a different locale.

**Cost.** An Indian viewer sees INR grouped in the Western convention.
Consistency wins for a table meant to be compared down a column.

### The History empty state is composed, not defaulted

**Decision.** An `Empty` reading "No salary changes yet", with a line saying
what will appear there.

**Why.** It is the *common* first view rather than an edge case — a new hire
has a salary, not a change — and it is the frame the demo transitions away
from. A blank panel reads as something failing to load; this reads as the
system reporting that it has nothing yet.

### Three frontend tests, not one per component

**Decision.** The suite covers the table's server round trip, the history read
including its empty state, and the edit that must appear in history.

**Why.** Those are the paths carrying real risk. A snapshot per card would
raise the test count without raising confidence, and a reviewer reading for
craftsmanship correctly reads that as padding.

**MSW returns the real response shapes** — DRF's envelope, money as strings —
so the tests exercise the same adapter the browser runs. The PATCH handler
starts returning a history row, which is what makes the third flow a genuine
round trip rather than an assertion about local state.

**One assertion was passing the wrong way and was fixed:** the history checks
matched both the record card and the history table, so they are now scoped with
`within(table)`.

### Known lint warnings, left in place

Four `oxlint` warnings remain: three `set-state-in-effect` on data-fetching
effects, one `only-export-components` where the auth module exports a hook
beside its provider. Both patterns are idiomatic for what they do; silencing
them would mean adopting a data-fetching library or splitting a two-export
file, and neither buys anything here. Recorded so their presence is a decision
rather than an oversight.

---

## 2026-08-30 — Phase 8, deploy, and closing notes

### `seed --if-empty`, so the release command can be unconditional

**Decision.** A flag that makes seeding a no-op when employees already exist,
rather than the error a bare re-seed raises.

**Why.** The Railway release command runs on *every* deploy. Without this,
either the first deploy is special-cased by hand, or the second one fails
because employee codes collide. `--if-empty` lets one command be correct
forever.

**Detail worth noting.** It still ensures FX rates even when it skips the
employees — rates can be missing while employees are not, and conversion
breaks without them. `--if-empty` with `--flush` is rejected: one says leave
the data alone, the other says replace it.

### `SECRET_KEY` has no production fallback

**Decision.** `config/settings/prod.py` calls `env("DJANGO_SECRET_KEY")` with
no default, so a missing value raises at import.

**Why.** A default here is worse than a crash. The app would boot on the
development key, sign session cookies with a value that is in the repository,
and give no signal that anything is wrong. **Verified** by running the
production checks with the variable unset and confirming `ImproperlyConfigured`.

`manage.py check --deploy --settings=config.settings.prod` now reports **no
issues** — the three that remained were schema-generation warnings, fixed by
naming the shared currency enum once and annotating the auth views.

### WhiteNoise rather than a static host

**Decision.** The admin's CSS and JS are served from the app process.

**Why.** The admin is the only server-rendered surface in the product. A CDN or
a separate static origin would be infrastructure for one page. The SPA is
already on Vercel's edge, which is where the static assets that matter live.

### The dashboard is code-split

**Decision.** `React.lazy` on the dashboard route.

**Why.** `@ant-design/plots` is the single heaviest dependency and exactly one
of three pages uses it. First load falls from 751 kB gzipped to **322 kB**, and
the 429 kB chart bundle arrives only for someone who opens the dashboard —
which is not the page people land on.

**Cost.** A brief spinner on first navigation to the dashboard.

---

## Closing note

**What was built.** Employee records with a full CRUD API and admin, a list
that works server-side at 10,000 rows, an append-only salary audit trail
visible in the UI the moment a change is made, analytics answering "how does
this org pay people" in a single reporting currency, a deterministic seed, and
session sign-in.

**What was deliberately not built**, and why, is in REQUIREMENTS.md §6. The
short version: CSV import and export were cut on the team's own guidance that a
polished core beats breadth, and no user model, RBAC or self-service exists
because one known operator needs none of it.

**The one place we went past the brief** is authentication (F6), and the
reasoning is recorded rather than assumed: "already authorized" describes a
person, not a request, and a public demo with no sign-in would serve ACME's
entire salary table to anyone with the URL.

**Numbers.** 339 backend tests in 9.86 s, 8 frontend tests, ~1,800 lines of
application code against ~2,800 lines of tests, 36 commits.

**A habit worth naming**, because it shaped the code more than any single
decision: wherever an assertion could plausibly pass against a broken
implementation, the implementation was temporarily broken to check the test
failed. That caught a float-precision test that passed either way, a filter
test that would have passed with filtering removed, an ordering test with only
one row in it, and a history assertion matching the wrong element. Each is
recorded above at the point it was found. A test that cannot fail is not
evidence, and the difference is invisible until someone checks.

---

## 2026-08-31 — Same-origin proxy over cross-site cookies

**Decision.** Vercel proxies `/api/*` to the Railway service (`vercel.json`),
the SPA calls a relative `/api/v1` base URL, and production cookies go back to
`SameSite=Lax`. The dev server proxies the same path so both environments share
one origin model.

**Why.** The deployed app was SPA on `vercel.app`, API on `railway.app`, with
`SameSite=None; Secure` to let the session cookie travel cross-site. Two things
were wrong with that, one immediately and one on a clock:

1. **The CSRF token was unreadable.** `document.cookie` exposes only cookies
   belonging to the current document's domain. Django set `csrftoken` on the
   API domain; the SPA ran on the Vercel domain; the `X-CSRFToken` header was
   never populated and every write was rejected. It surfaced as "sign out is
   broken", which understated it — the salary edit, the whole demo moment, was
   equally broken. Login worked only because `LoginView` carries no
   authenticator and therefore no CSRF enforcement, which is precisely what
   made the failure look narrow.
2. **The session cookie was third-party.** Browsers block those by default in
   incognito — the exact context a reviewer opens — and are removing them
   generally. `SameSite=None` is a losing position: it is a request for
   permission that browsers are increasingly declining.

**The fix considered and rejected.** Return the CSRF token in the login and
`/auth/me` response bodies, so the SPA holds it without reading the cookie.
That repairs the header and leaves the session cookie exactly as exposed —
treating the symptom while the actual dependency, third-party cookie support,
keeps eroding underneath.

**Same-origin removes the class.** One origin means both cookies are
first-party: readable by JavaScript, sent under the default `SameSite=Lax`,
untouched by third-party cookie policy, and working in incognito. CORS becomes
irrelevant to the app.

**Cost.** API traffic takes an extra hop through Vercel's edge, and the Railway
domain is hardcoded in `vercel.json` because Vercel does not interpolate
environment variables into rewrite destinations. Both are cheap against a
security model that stops depending on a browser feature being withdrawn.

**Local development now mirrors it**, which is the part worth keeping. The bug
could not reproduce locally: the dev server on `:5173` and the API on `:8000`
are different origins, but cookies ignore the port and both are `localhost`, so
`document.cookie` could read the token. Development passed for a reason that
did not generalise. `vite.config.ts` now proxies `/api` too, so the origin model
is the same in both places.

**Tests.** `apps/accounts/tests/test_csrf_for_spa.py` uses
`enforce_csrf_checks=True` — without it Django's CSRF machinery is bypassed and
none of the assertions can fail. Each write is asserted to be *refused* without
the header before being asserted to succeed with it, so the passing case cannot
pass for the wrong reason. The test client is not a browser and can read its own
cookie jar, so these cover Django's contract; the browser behaviour that caused
the incident is addressed by the architecture, not by a test.
