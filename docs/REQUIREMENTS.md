# Requirements — ACME Salary Management

**Author:** Kunal Kejriwal · **Status:** Scope confirmed · **Scope:** Take-home assessment (Incubyte)

One page on *what* is being built and, just as deliberately, what is not.
Companion docs: `ARCHITECTURE.md` (how), `DECISIONS.md` (trade-off log),
`AI_USAGE.md` (AI workflow).

---

## 1. Problem

ACME's HR manager maintains salary data for ~10,000 employees across multiple
countries in a spreadsheet. It does not survive multiple currencies, gives no
reliable org-wide view of cost, and has no history of who changed what.

This replaces that workflow with a small internal web application.

---

## 2. Persona

A single HR manager, already authorized, operating an internal tool. There is
no second role and no employee-facing surface (§7).

---

## 3. Confirmed Scope

These were raised with the Incubyte team and answered directly. They are
settled decisions, not working assumptions.

| Question | Confirmed answer |
|---|---|
| **Currency model** | Confirmed as proposed. Each employee's salary is stored in their native local currency; org-wide totals normalize to a single base reporting currency (USD) via a simple seeded exchange-rate table. |
| **Employee schema** | Full ownership to define it. Confirmed shape: **ID, Name, Department, Job Title, Country, Base Salary, Currency, Joined Date.** |
| **Populating 10,000 records** | A clean database seed script using Faker is *completely sufficient*. Bulk CSV import with row-by-row validation is **not expected**. |
| **CSV import** | Explicitly **optional stretch** (F3, §6). |
| **Authentication** | Explicitly **scoped out** (§7). The application is internal and the user is an already-authorized single HR manager. |
| **Employee self-service portal** | Explicitly scoped out. |
| **RBAC / multi-role permissions** | Explicitly scoped out — building a user model or role matrix upfront would be over-engineering. Future auth/IdP considerations are documented instead. |
| **Grading emphasis** | Clean code architecture, server-side performance across 10,000 records, and strong documentation — over speed of submission. |

---

## 4. Data Model

The confirmed schema, as implemented:

| Confirmed field | Implementation | Note |
|---|---|---|
| ID | `id` (UUID) + `employee_code` | UUID primary key; `employee_code` is the human-readable HR identifier |
| Name | `first_name`, `last_name` | Split so the list view can sort and index on surname |
| Department | `department` | Indexed |
| Job Title | `job_title` | Indexed; also an analytics grouping (F5) |
| Country | `country` | ISO 3166-1 alpha-2, indexed |
| Base Salary | `salary_amount` | `Decimal`, never float |
| Currency | `currency` | ISO 4217, constrained to the eight supported codes |
| Joined Date | `joined_on` | Date |

Two derived columns support the confirmed currency model:

- `salary_usd` — the base salary normalized to USD at write time, so every
  cross-country aggregate is a plain ORM aggregation.
- `salary_change` — an append-only audit trail of salary movements (F6).

---

## 5. Core Features

Built in full.

### F1 — Employee record and CRUD
Create, view, update and delete an employee carrying every field in §4,
including **job title**. Salary is captured in the employee's local currency
and normalized to USD on write. Validation rejects negative salaries and
unsupported currencies.

### F2 — Employee list
Server-side pagination, ordering and filtering across country, department,
job title, currency and salary range, plus free-text search on name and
employee code. The browser never receives 10,000 rows.

### F4 — CSV export
Download the current filtered view as CSV, so data can round-trip back into a
spreadsheet when needed.

### F5 — Analytics
Org-wide figures, all in the USD reporting currency:
headcount, total and average cost, median; distribution histogram; and
per-group breakdowns (headcount, average, median, p10/p90) **by country, by
department, and by job title**.

### F6 — Salary history
Every salary change appends an audit row recording the old and new amounts,
their currencies, who made the change and when. Viewable per employee.

---

## 6. Stretch — build last, only if time permits

### F3 — Bulk CSV import
Upload a CSV of employees, validate row by row, insert the valid rows in
batches and report per-row failures with a downloadable error report.

Confirmed by the Incubyte team as **not expected**: the 10,000 records are
populated by the seed script instead. The design is retained in
`ARCHITECTURE.md` §5 and is attempted only after every core feature and the
documentation are complete. Nothing in the core scope depends on it.

---

## 7. Deliberately Out of Scope

| Not built | Why | Future path |
|---|---|---|
| **Authentication and login** | Per team guidance. The application is internal and the user is an already-authorized single HR manager; a login screen for one known operator adds surface without adding safety | SSO/IdP at the edge; Django groups for roles |
| **RBAC / multi-role permissions** | Per team guidance — over-engineering ahead of a second persona | Django groups and permissions enforced in the service layer |
| **Employee self-service portal** | Per team guidance; one persona in scope | `/me` endpoints on the same UI-agnostic API |
| Live FX rate feed | A seeded static table is deterministic and testable; the staleness trade-off is documented | Daily rate ingestion with effective-dated rates |
| Async import workers (Celery/broker) | Three deployable services for a job that does not exist in core scope | >1M rows or concurrent imports |
| Payroll execution / payslips | Managing salary data is not paying people | Separate bounded context, integrating over the same API |
| Caching / read replicas | Every query is milliseconds at 10k rows | ~1M+ employees or heavy concurrent analytics |

---

## 8. Success Criteria

The build is done when:

1. **Seed populates 10,000 realistic records deterministically** — one command,
   `Faker(seed=42)`, same data on every run, with salaries distributed
   plausibly per country and job title rather than uniformly.
2. **List and analytics endpoints stay performant across 10,000 records**, with
   query-count and timing evidence committed — not asserted. Query counts are
   pinned by tests so an N+1 fails the suite rather than the demo.
3. Salary data is correct across currencies: `Decimal` throughout, no float
   arithmetic anywhere in the money path, conversions tested against
   hand-computed values.
4. Every salary change is auditable — old and new amounts, currencies, actor
   and timestamp.
5. The test suite is fast, deterministic and runs with no external services.
6. Architecture, scope boundaries and trade-offs are documented well enough for
   a reviewer to follow the reasoning without reading the code.

---

## 9. Non-Functional Requirements

- **Correctness of money** — `Decimal` end to end; float is rejected at the
  boundary rather than coerced.
- **Server-side everything** — pagination, filtering, sorting and aggregation
  happen in the database.
- **Determinism** — seeded fixtures and a fixed Faker seed; no network, no
  sleeps, no time-dependent assertions in tests.
- **Thin views, fat services** — business logic sits in tested service modules,
  independent of HTTP.
