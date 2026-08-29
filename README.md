# ACME Salary Management

Salary data management for ACME's HR team — replacing an Excel workflow for
~10,000 employees across multiple countries.

Django 5 + DRF API, React + TypeScript + Ant Design SPA. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and its rationale,
and [docs/DECISIONS.md](docs/DECISIONS.md) for the trade-off log.

> **Status: scaffold.** The project structure, tooling and test harness are in
> place. Domain models, endpoints and UI pages are built phase by phase — see
> [docs/BUILD_PROMPTS.md](docs/BUILD_PROMPTS.md).

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
python manage.py runserver
```

The API is then at <http://localhost:8000>:

| URL | What |
|---|---|
| `/api/v1/` | API root (endpoints land in later phases) |
| `/api/docs/` | Swagger UI |
| `/api/schema/` | OpenAPI schema |
| `/admin/` | Django admin — needs `python manage.py createsuperuser` |

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

Run the backend and the frontend side by side in two terminals.

---

## Layout

```
config/            settings package (base/dev/prod/test), urls, wsgi, asgi
apps/
  core/            shared: currencies, FX rates, seed command
  employees/       employee model, CRUD API, salary audit trail
  imports/         CSV import pipeline and error reports
  analytics/       aggregate queries
  */services.py    business logic — views stay thin
  */tests/         tests colocated per app
frontend/          Vite + React + TypeScript + Ant Design SPA
  src/api/         typed API client
requirements/      base / dev / prod dependency sets
docs/              architecture, decisions, build prompts
```

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
