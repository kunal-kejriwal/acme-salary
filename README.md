# ACME Salary Management

Salary data management for ACME's HR team — replacing an Excel workflow for
~10,000 employees across multiple countries.

Django 5 + DRF API, React + TypeScript + Ant Design SPA. See
[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) for scope and its confirmed
boundaries, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and its
rationale, and [docs/DECISIONS.md](docs/DECISIONS.md) for the trade-off log.

Build progress and the prompts used are in
[docs/BUILD_PROMPTS.md](docs/BUILD_PROMPTS.md).

---

## Requirements

- Python 3.12 or newer (developed against 3.14)
- Node.js 20 or newer

No database server is required for development or tests — both default to
SQLite. Postgres is the production database and can be used locally by setting
`DATABASE_URL`.

---

## Backend

```bash
# From the repository root
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements/dev.txt

cp .env.example .env            # optional; sensible defaults apply without it

python manage.py migrate
python manage.py createsuperuser   # this is the HR manager's account
python manage.py seed --count 10000
python manage.py runserver
```

The superuser is the only account: authentication is a session over Django's
built-in user, with no bespoke user model (REQUIREMENTS.md F6). The same
credentials sign in to the SPA and to `/admin`.

The API is then at <http://localhost:8000>:

| URL | What |
|---|---|
| `/api/v1/employees/` | Employee list and CRUD |
| `/api/v1/analytics/summary/` | Headcount and cost, USD |
| `/api/docs/` | Swagger UI |
| `/api/schema/` | OpenAPI schema |
| `/admin/` | Django admin, back-office over the same data |

### Tests

```bash
pytest                 # in-memory SQLite, no external services
pytest --cov           # with coverage
```

The suite must stay under 10 seconds and must not depend on network or a
database server.

### Running against Postgres

Set `DATABASE_URL` and re-run migrations:

```bash
export DATABASE_URL=postgres://acme:acme@localhost:5432/acme_salary
python manage.py migrate
```

Tests always use in-memory SQLite regardless of this setting.

---

## Frontend

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173
```

| Command | What |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run build` | Type-check and build to `frontend/dist` |
| `npm run test` | Vitest + Testing Library |
| `npm run lint` | oxlint |

The API base URL comes from `VITE_API_BASE_URL` (see `frontend/.env.example`)
and defaults to `http://localhost:8000/api/v1`. The dev server origin is
already in the backend's `CORS_ALLOWED_ORIGINS`.

Run the backend and the frontend side by side in two terminals, then sign in
at <http://localhost:5173> with the superuser you created.

### Pages

| Page | What |
|---|---|
| Employees | Server-side table over all 10,000 records: pagination, sorting, filters (country, department, job title, currency, USD salary range) and search |
| Employee detail | The full record, an edit drawer, and the salary change history |
| Dashboard | Headcount and cost summary, plus median salary by country, department and job title |

### The two-minute demo

1. Sign in.
2. Filter the employee list to a country, then sort by USD salary. 10,000
   records, every query server-side.
3. Open an employee. The History tab reads **No salary changes yet**.
4. Edit their salary and save.
5. History now shows the change: old and new amount, currency, who made it
   and when, without a reload. The audit row is written by the same service
   call that changed the pay.
6. Open the Dashboard for the org-wide view in USD.

---

## Layout

```
config/            settings package (base/dev/prod/test), urls, wsgi, asgi
apps/
  accounts/        session sign-in over Django's built-in user
  core/            shared: currencies, FX rates, seed command
  employees/       employee model, CRUD API, salary audit trail
  analytics/       aggregate queries
  */services.py    business logic — views stay thin
  */tests/         tests colocated per app
frontend/          Vite + React + TypeScript + Ant Design SPA
  src/api/         typed API client, CSRF, Table-to-DRF adapter
  src/pages/       login, employees, employee detail, dashboard
  src/test/        three-flow suite with MSW
requirements.txt   production dependencies, flat and pinned
requirements/dev.txt  the above plus test tooling
scripts/           benchmark.py, reproducible performance measurements
docs/              architecture, decisions, build prompts
```

---

## Deployment

The API runs on Railway (Gunicorn + managed Postgres), the SPA on Vercel. No
containers: one process and one managed database is not something worth
orchestrating.

### API — Railway

1. Point a new Railway service at this repo and add a **PostgreSQL** plugin.
   `DATABASE_URL` is injected automatically.
2. Set the remaining variables:

   | Variable | Value |
   |---|---|
   | `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
   | `DJANGO_SECRET_KEY` | a long random string — `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"` |
   | `DJANGO_ALLOWED_HOSTS` | your Railway domain |
   | `CORS_ALLOWED_ORIGINS` | your Vercel URL |
   | `CSRF_TRUSTED_ORIGINS` | your Vercel URL |

3. Deploy. [`railway.json`](railway.json) runs `migrate` and
   `seed --if-empty --count 10000` before each release, so a fresh database
   fills itself and later deploys leave the data alone.
4. **Create the HR account**, once, from the Railway shell:

   ```bash
   python manage.py createsuperuser
   ```

   This is the only account. It signs in to both the SPA and `/admin`.

`config/settings/prod.py` has no fallback for `DJANGO_SECRET_KEY` — a deploy
missing it fails at boot rather than quietly running on the development key.
`python manage.py check --deploy --settings=config.settings.prod` reports no
issues.

### SPA — Vercel

Import the repo, set **Root Directory** to `frontend`, and set one variable:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<your-railway-domain>/api/v1` |

[`frontend/vercel.json`](frontend/vercel.json) rewrites unknown paths to the
SPA shell, so reloading `/employees/<id>` does not 404 at the edge.

Because the two live on different domains, the session cookie has to survive a
cross-site request: `config/settings/prod.py` sets `SameSite=None` with
`Secure=True`, which browsers only honour together.

### Demo

- **Live app:** _(deploy and paste the Vercel URL here)_
- **API docs:** _(your Railway domain)_`/api/docs/`
- **Walkthrough video:** _(paste link here)_

---

## Configuration

All environment-driven; see [`.env.example`](.env.example) for the full list.

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | `config.settings.prod` in production |
| `DJANGO_SECRET_KEY` | insecure placeholder | Required in production |
| `DJANGO_DEBUG` | `True` in dev | Always `False` in production |
| `DJANGO_ALLOWED_HOSTS` | localhost | Required in production |
| `DATABASE_URL` | SQLite file | Required in production |
| `CORS_ALLOWED_ORIGINS` | Vite dev server | Required in production |

No secrets are committed.
