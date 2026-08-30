# Requirements — ACME Salary Management

**Author:** Kunal Kejriwal · **Status:** Scope locked · **Scope:** Take-home assessment (Incubyte)

One page on *what* is being built and, just as deliberately, what is not.
Companion docs: `ARCHITECTURE.md` (how), `DECISIONS.md` (trade-off log),
`AI_USAGE.md` (AI workflow).

**Scope authority:** the assessment brief and the Incubyte team's clarification
email. Nothing else.

---

## 1. Problem

ACME's HR manager maintains salary data for ~10,000 employees across multiple
countries in a spreadsheet. It does not survive multiple currencies, gives no
reliable org-wide view of cost, and has no history of who changed what.

This replaces that workflow with a small internal web application.

---

## 2. Persona

A single HR manager, already authorized, operating an internal tool. There is
no second role and no employee-facing surface (§6).

---

## 3. Confirmed Scope

These were raised with the Incubyte team and answered directly. They are
settled decisions, not working assumptions.

| Question | Confirmed answer |
|---|---|
| **Currency model** | Confirmed as proposed. Each employee's salary is stored in their native local currency; org-wide totals normalize to a single base reporting currency (USD) via a simple seeded exchange-rate table. |
| **Employee schema** | Full ownership to define it. Confirmed shape: **ID, Name, Department, Job Title, Country, Base Salary, Currency, Joined Date.** |
| **Populating 10,000 records** | A clean database seed script using Faker is *completely sufficient*. Bulk CSV import with row-by-row validation is **not expected**. |
| **CSV import** | Optional stretch only — and cut (§6). |
| **Authentication** | Explicitly **scoped out**. The application is internal and the user is an already-authorized single HR manager. |
| **Employee self-service portal** | Explicitly scoped out. |
| **RBAC / multi-role permissions** | Explicitly scoped out — building a user model or role matrix upfront would be over-engineering. Future auth/IdP considerations are documented instead. |
| **Grading emphasis** | Clean code architecture, server-side performance across 10,000 records, and strong documentation — over breadth or speed of submission. |

The Django **admin** is the HR manager's credential and back-office: since no
bespoke login is built, the admin superuser is the account that exists, and it
gives a working view over employees and the salary audit trail at zero cost.

---

## 4. Data Model

The confirmed schema, as implemented:

| Confirmed field | Implementation | Note |
|---|---|---|
| ID | `id` (UUID) + `employee_code` | UUID primary key; `employee_code` is the human-readable HR identifier |
| Name | `first_name`, `last_name` | Split so the list view can sort and index on surname |
| Department | `department` | Indexed; an analytics grouping |
| Job Title | `job_title` | Indexed; an analytics grouping |
| Country | `country` | ISO 3166-1 alpha-2, indexed; an analytics grouping |
| Base Salary | `salary_amount` | `Decimal`, never float |
| Currency | `currency` | ISO 4217, constrained to the eight supported codes |
| Joined Date | `joined_on` | Date |

Two derived stores support the confirmed currency model:

- `salary_usd` — the base salary normalized to USD at write time, so every
  cross-country aggregate and range filter is a plain indexed comparison.
- `salary_change` — an append-only audit trail of salary movements (F3).

---

## 5. Features

Exactly these five. Built in full.

### F1 — Employee records
Create, view, update and delete an employee carrying every field in §4. Salary
is captured in the employee's local currency and normalized to USD on write.
Validation rejects negative salaries and unsupported currencies. Available as a
REST API and, for back-office use, through the Django admin.

### F2 — List at scale
The employee list works server-side at 10,000 records: page-number pagination,
filters on country, department, job title, currency and a **USD salary range**,
free-text search on name and employee code, and column ordering that is
**stable** — every sort carries a tiebreaker so rows cannot straddle a page
boundary. The browser never receives 10,000 rows.

### F3 — Salary change history
Every salary change appends an audit row recording the old and new amounts,
their currencies, who made the change and when. Exposed per employee and shown
on the employee detail view. A change is visible in the history immediately
after it is made.

### F4 — Analytics
Answers "how does this org pay people", all in the USD reporting currency:

- **Summary** — headcount, total annual cost, average, median.
- **By country**, **by department**, **by job title** — headcount, average,
  median, min and max per group.

### F5 — Deterministic 10k seed
One command populates 10,000 realistic employees. Same seed, same data, every
run. Salaries are realistic *in local currency* and driven by country and job
title, so the analytics reflect a plausible organization rather than noise.

---

## 6. Deliberately Out of Scope

| Not built | Why | Future path |
|---|---|---|
| **CSV bulk import** | Team guidance: not expected — the seed covers the 10,000 records. Optional stretch; cut to keep the core polished | Stream-parse and validate row by row, batch-insert the valid rows, report per-row failures. `ARCHITECTURE.md` §8 carries the design |
| **CSV export** | Same call: breadth traded for a polished core | A streaming response over the filterset the list view already uses |
| **Authentication and login page** | Per team guidance. The application is internal and the user is an already-authorized single HR manager; the Django admin login is the credential that exists | SSO/IdP at the edge; Django groups for roles |
| **RBAC / multi-role permissions** | Per team guidance — over-engineering ahead of a second persona | Django groups and permissions enforced in the service layer |
| **Employee self-service portal** | Per team guidance; one persona in scope | `/me` endpoints on the same UI-agnostic API |
| Live FX rate feed | A seeded static table is deterministic and testable; the staleness trade-off is documented | Daily rate ingestion with effective-dated rates |
| Containerization | Nothing to orchestrate: one process, one managed database | Multi-service deployment |
| Payroll execution / payslips | Managing salary data is not paying people | Separate bounded context over the same API |
| Caching / read replicas | Every query is milliseconds at 10k rows, with measured evidence | ~1M+ employees or heavy concurrent analytics |

---

## 7. Success Criteria

The build is done when:

1. **Seed populates 10,000 realistic records deterministically** — one command,
   fixed seed, same data on every run, with salaries distributed plausibly per
   country and job title rather than uniformly.
2. **List and analytics endpoints stay performant across 10,000 records**, with
   query-count and timing evidence committed — not asserted. Query counts are
   pinned by tests so an N+1 fails the suite rather than the demo.
3. Salary data is correct across currencies: `Decimal` throughout, no float
   arithmetic anywhere in the money path, conversions tested against
   hand-computed values.
4. Every salary change is auditable — old and new amounts, currencies, actor
   and timestamp — and visible in the UI immediately after the change.
5. The test suite is fast, deterministic and runs with no external services.
6. Architecture, scope boundaries and trade-offs are documented well enough for
   a reviewer to follow the reasoning without reading the code.

---

## 8. Non-Functional Requirements

- **Correctness of money** — `Decimal` end to end; float is rejected at the
  boundary rather than coerced.
- **Server-side everything** — pagination, filtering, sorting and aggregation
  happen in the database.
- **Determinism** — seeded fixtures and a fixed seed; no network, no sleeps, no
  time-dependent assertions in tests.
- **Thin views, fat services** — business logic sits in tested service modules,
  independent of HTTP.
