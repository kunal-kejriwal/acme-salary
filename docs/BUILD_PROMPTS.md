# BUILD_PROMPTS — Claude Code phase prompts (rev 2, final scope)

Run these one at a time, in order. Review the diff and test output after each
phase before starting the next. Committed as part of `AI_USAGE.md` evidence.

**Scope authority:** the assessment brief + Incubyte's clarification email.
Nothing else.

**In:** employee records, list at 10k (pagination/filter/search/order), salary
editing with audit history, analytics that answer "how does the org pay
people", seed, deploy, demo.

**Out entirely:** CSV import/export, Docker, async, employee self-service, a
bespoke user model, RBAC.

**Added past the brief, deliberately:** session sign-in (Phase 6b). "Already
authorized" has to mean something at the HTTP boundary once the demo is
public.

Phases 0–4 are shipped: scaffold, core money layer, employee model + CRUD,
list at scale, deterministic seed.

---

## Phase 5 — Docs re-scope (no code)
```
Align all docs with the final scope above, in one commit:
"docs: re-scope to brief + team clarifications".

- REQUIREMENTS.md: features are exactly — F1 employee records (CRUD via API,
  admin as back-office), F2 list at scale (pagination, filters incl. salary_usd
  range, search, stable ordering), F3 salary change history (audit trail,
  shown on employee detail), F4 analytics (summary + by-country + by-title +
  by-department, USD), F5 deterministic 10k seed. Move CSV import AND export
  to Deliberately Out ("team guidance: optional stretch; cut to keep the core
  polished"). Auth stays out per team guidance; Django admin noted as the HR
  manager's credential and back-office.
- ARCHITECTURE.md: remove import endpoints and §5 import pipeline (fold a
  two-line "stretch path" note into §9). Remove export endpoint. §10 already
  no-Docker; verify. Analytics endpoints stay as specced minus /distribution
  — keep summary, by-country, by-department, by-title.
- DECISIONS.md: dated entry — final scope locked to brief + clarifications;
  one line on why (their email: clean core + performance + docs over breadth).
- Leave git history alone; just ensure current docs carry no import/export/
  login references. Grep to verify: "import", "export", "login", "compose".
```

## Phase 6b — Session auth (backend) — SHIPPED
```
TDD minimal session auth. No new user model — the seed superuser is the HR
account.
- POST /api/v1/auth/login (username/password -> session), POST /auth/logout,
  GET /auth/me (user or 401).
- DRF defaults: SessionAuthentication + IsAuthenticated project-wide; confirm
  every existing endpoint now 403s unauthenticated. Enumerate routes
  dynamically from the URLconf (excluding the auth endpoints) so later phases
  are covered with zero test edits.
- Settings for split-domain deploy: CORS_ALLOW_CREDENTIALS, CSRF_TRUSTED_ORIGINS,
  SESSION_COOKIE_SAMESITE/SECURE + CSRF equivalents env-driven (lax in dev).
- REQUIREMENTS.md: auth becomes a feature, framed as beyond team guidance,
  deliberately. DECISIONS.md dated entry.
```

## Phase 6 — Analytics API
```
TDD apps/analytics, all values in USD, read-only endpoints:

- GET /api/v1/analytics/summary — headcount, total annual cost, average,
  median.
- GET /api/v1/analytics/by-country, /by-department, /by-title — headcount,
  average, median, min, max per group, ordered by headcount desc.

Rules: ORM aggregation only; median via a portable expression that passes on
SQLite (record approach in DECISIONS.md). Tests: hand-computed fixture
(~8 employees, mixed currencies) asserting exact values — median must
discriminate from mean on the fixture (skew it); empty-DB behavior (zeros,
not 500s); assertNumQueries pinned per endpoint (one aggregate query each,
no per-group queries).

Then: append these endpoints to scripts/benchmark.py, run at 10k, extend the
timing table in DECISIONS.md.
```

## Phase 7 — Frontend
```
Build the SPA against the running API. React 18 + TS + Ant Design, typed API
client module, react-router. Pages:

1. Login — form posting to /auth/login, redirecting to Employees on success
   and surfacing the API's error message on failure. The app boots by calling
   /auth/me: 401 routes to Login, 200 routes to the requested page. The API
   client sends X-CSRFToken from the csrftoken cookie on unsafe requests.
2. Employees (home) — Table wired to /employees: server-side pagination,
   column sorting, filter bar (country, department, job title, currency,
   salary_usd min/max), search box (name/code). Row click → detail.
3. Employee detail — record card (all fields, local salary + USD); "Edit"
   opening a drawer form (validation mirrors API errors); History tab —
   table of salary changes (old → new, currency, changed_by, date) from
   /employees/{id}/salary-history, empty-state message when none. A salary
   edit must refresh both the card and the History tab (this is the demo
   moment: change is visible in history immediately).
4. Dashboard — stat cards from /analytics/summary; three bar charts
   (by-country, by-department, by-title) via @ant-design/plots, labelled USD.

README points at /admin (same superuser) for back-office.

Vitest + Testing Library, MSW for API mocks: table renders server page and
passes filter params through; detail page shows history rows; salary edit
posts and re-renders history. Keep tests to those three flows — targeted,
not exhaustive. Commit per page.
```

## Phase 8 — Deploy + demo prep
```
- Prod settings hardened: SECRET_KEY required from env (no fallback),
  DEBUG=False, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS env-driven, WhiteNoise
  for admin static.
- Railway: Nixpacks, gunicorn, release command `migrate && seed --if-empty
  --count 10000` (implement --if-empty: no-op when employees exist, tested).
- Vercel: frontend/, VITE_API_BASE_URL env; README deploy section with both
  URLs and the superuser bootstrap step.
- Final pass: full suite timing, benchmark table refreshed, DECISIONS.md
  closing entry, README demo-video link placeholder.
```
