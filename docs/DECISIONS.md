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
