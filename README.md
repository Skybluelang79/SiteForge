# SiteForge

Enterprise construction management platform: project controls, documents and drawings, field
operations, RFIs and submittals, financials, quality and safety, reporting, integrations and a
real-time notification layer.

- **Backend:** Django 6.1, Django REST Framework, Channels, Celery, PostgreSQL/SQLite
- **Frontend:** Angular standalone components (zoneless), signal-based state
- **Runtime:** Docker Compose with PostgreSQL, Redis, nginx, Mailpit

```
backend/   Django project and domain apps (apps/*), tests, seed command
frontend/  Angular application served by nginx in production
docs/      Conventions and operations notes
```

## Quick start (local, no Docker)

Prerequisites: Python 3.12+ (project venv uses 3.14), Node 22+ / 24.

### Backend

```powershell
# from the repository root
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py seed_dev_data --reset
..\.venv\Scripts\python.exe manage.py runserver
```

The API is available at `http://localhost:8000/api/v1/` and Swagger UI at
`http://localhost:8000/api/docs/`.

SQLite is used when `DATABASE_URL` is unset. Redis is optional locally: set
`USE_IN_MEMORY_CHANNEL_LAYER=True` in `backend/.env` to avoid websocket connection noise, and
`CELERY_TASK_ALWAYS_EAGER=True` to run background tasks inline.

### Frontend

```powershell
Set-Location frontend
npm install
npm start
```

`ng serve` runs at `http://localhost:4200` and proxies `/api` to the backend.

### Demo accounts

The seed command creates the `acme-demo` organization, the **Harbor Point Tower** project, and:

| Email | Role |
| --- | --- |
| `owner@demo.siteforge.test` | owner |
| `pm@demo.siteforge.test` | admin / project manager |
| `super@demo.siteforge.test` | member / superintendent |
| `viewer@demo.siteforge.test` | viewer |

Password for all demo users: `DemoPass123!`.

## Docker Compose

```powershell
Copy-Item .env.example .env   # optional override of compose defaults
docker compose up --build -d
docker compose --profile seed run --rm seed
```

| Service | URL |
| --- | --- |
| Web app (nginx + Angular) | http://localhost:8080 |
| API | http://localhost:8000/api/v1/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| Django admin | http://localhost:8000/admin/ |
| Mailpit | http://localhost:8025 |

Services: `db` (PostgreSQL 17), `redis`, `backend` (Daphne ASGI), `worker` (Celery),
`beat` (Celery beat), `frontend` (nginx), `mailpit`. Migrations and `collectstatic` run in the
backend entrypoint. Set `SEED_DEMO_DATA=1` to reseed on container start, or use the one-off
`seed` profile as shown above.

## Tests

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q --no-header
```

The suite covers the original vertical slice plus cross-module workflows (financial approvals,
quality sign-off and punch lists, RFI responses and overdue sweeps, report export jobs, metric
snapshots, and integration credentials/webhooks).

Useful checks:

```powershell
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe makemigrations --check --dry-run
Set-Location ..\frontend
npm run build
```

## What is implemented

- **Auth & organizations:** JWT access/refresh, MFA (TOTP + recovery codes), sessions, invitations,
  role-based permission keys, active organization via `X-Organization-Id`.
- **Projects:** projects, team membership, milestones, contracts, activity feed, dashboard KPIs.
- **Documents & drawings:** folders, versioned documents, drawing sets, revisions and reviews.
- **Field:** daily logs, labour, equipment, weather, photos, observations.
- **Tasks:** tasks, dependencies, progress and completion sync.
- **RFIs & submittals:** RFIs with official responses and overdue sweep, submittals, approval
  chains, comments.
- **Financials:** cost codes, budgets and lines, commitments, purchase orders, invoices, change
  orders, retentions, forecasts; approval services with row locking.
- **Quality & safety:** inspections and items, sign-off, defects, punch lists, safety incidents,
  corrective actions.
- **Reports:** report definitions, dashboards, export jobs (CSV/JSON), metric snapshots and daily
  metrics collection.
- **Integrations:** API applications with hashed credentials, HMAC-signed webhooks with retry and
  delivery history, webhook event log.
- **Notifications:** persisted notifications, WebSocket fan-out, audit trail.
- **Frontend:** login + MFA, dashboard, project portfolio and detail workspace, resource pages for
  documents, drawings, field logs, tasks, RFIs, financials, quality, reports and integrations,
  profile/permissions view, project and organization switching.

See `ARCHITECTURE.md` for the design, `docs/CONVENTIONS.md` for coding rules, and
`docs/BACKUPS.md` for operations guidance.
