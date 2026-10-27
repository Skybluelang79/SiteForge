# Architecture — Enterprise Construction Management Platform ("SiteForge")

Working name: **SiteForge**. Original branding; no proprietary Procore code, assets, or designs are used.

## 1. Goals

A multi-tenant construction management platform covering documents, drawings, field reports,
tasks/schedules, RFIs/submittals, financials, quality/safety, reporting, integrations, and admin.

Every UI feature is backed by a real REST endpoint and PostgreSQL persistence. No static mock UI.

## 2. High-level topology

```
┌────────────┐   HTTPS/JSON    ┌──────────────────────────────┐
│  Angular   │ ──────────────► │  Django (ASGI: Daphne)       │
│  SPA       │   /api/v1/...   │  ├─ DRF REST API             │
│  (nginx)   │ ◄────────────── │  ├─ OAuth2 provider (DOT)    │
└────────────┘   WebSocket     │  ├─ Channels consumers       │
      │                        │  ├─ Celery workers           │
      │                        │  └─ Static/media via S3 or   │
      │                        │      local disk (dev)        │
      │                        └───────┬──────────┬───────────┘
      │                                │          │
      ▼                                ▼          ▼
   Redis (channels layer,        PostgreSQL   S3-compatible
   Celery broker/result)                      object storage
```

Docker Compose services: `postgres`, `redis`, `backend` (ASGI), `worker` (Celery),
`beat` (Celery beat), `frontend` (nginx serving Angular build + proxying `/api`), `mailpit` (dev mail).

## 3. Backend layout

```
backend/
  manage.py
  requirements.txt / requirements-dev.txt
  config/            # settings package, urls, asgi/wsgi, celery app, logging
  apps/
    common/          # UUIDBase, TimeStampedModel, audit helpers, permissions,
                     # pagination, throttles, exceptions, idempotency, tests utils
    accounts/        # custom User, MFA (TOTP), profile, sessions, password reset
    organizations/   # Organization, Membership, Role, permission matrix, Invitation
    projects/        # Project, ProjectMember, Milestone, ActivityFeed, project switches
    documents/       # Document, DocumentVersion, folders, metadata, secure download
    drawings/        # Drawing, DrawingRevision, review workflows
    field/           # DailyLog, LabourEntry, WeatherEntry, EquipmentEntry,
                     # FieldPhoto, Observation
    tasks/           # Task, TaskDependency, schedule fields, progress
    rfis/            # RFI, Submittal, SubmittalItem, comments, approval chains
    financials/      # CostCode, Budget, BudgetLine, Commitment(Contract), PurchaseOrder,
                     # Invoice, ChangeOrder, Retention, Forecast
    quality/         # Inspection, InspectionItem, Defect, PunchList, PunchListItem,
                     # SafetyIncident, CorrectiveAction
    reports/         # saved report configs, analytics endpoints, CSV/PDF-ish exports
    integrations/    # ApiApplication (OAuth clients), webhooks, deliveries, health
    notifications/   # Notification, preferences, Channels consumer
    audit/           # AuditEvent, admin console read APIs
  seed/management/commands/seed_dev_data.py
  tests/             # cross-app + per-app tests live next to apps too
```

Conventions are documented in `docs/CONVENTIONS.md` (models, serializers, viewsets,
permissions, filters, tests). All apps follow them.

## 4. Tenancy & authorization model

- **Tenant boundary = Organization.** Every business row belongs to an organization
  (directly via `organization_id` or transitively via `project.organization`).
- Users join organizations through `Membership` (role-scoped). Projects add
  `ProjectMember` rows for per-project role overrides.
- `Role` is an organization-scoped named role (Owner, Admin, Member, Viewer, plus
  company-side roles) with a JSON permission matrix; platform-defined permission keys
  live in `common/permissions.py` (`PERMISSION_MATRIX`).
- Enforcement layers (all must hold):
  1. **Queryset scoping** — every list queryset filters by the request's active
     organization membership and project access (`OrganizationScopedQuerysetMixin`).
  2. **Object permissions** — `DjangoModelPermissions`-style checks + custom
     `IsOrgMember`, `IsProjectMember`, `HasPermission("key")` classes.
  3. **Serializer validation** — nested writes re-check org/project belonging.
  4. **Background jobs** — Celery tasks receive explicit object ids and re-resolve
     with the same scoping helpers; cross-org references raise `PermissionDenied`.
  5. **File downloads** — mediated by signed, expiring URLs or authenticated
     endpoints that re-check project access (no public media buckets).
  6. **WebSockets** — consumers authenticate (JWT in query string / session) and
     group names embed `org_id`/`project_id`; membership is verified on connect.
- The active organization is selected per request via `X-Organization-Id` header
  (or JWT claim fallback) and cached on `request.membership`.

## 5. Identity & auth

- **Primary login:** email + password → JWT (simplejwt) access (short) + refresh (rotating) tokens.
- **MFA:** `django-otp` TOTP. Enroll → confirm with a code → required on login
  (`POST /api/v1/auth/mfa/verify/` returns MFA-scoped token; recovery codes provided).
- **OAuth 2.0:** `django-oauth-toolkit` exposed at `/o/` for third-party integrations;
  API accepts either JWT or OAuth2 bearer tokens.
- Password reset via signed email link (dev: printed/Mailpit).

## 6. Real-time

Channels + Redis layer. Consumer `ws/notifications/` streams `Notification` events
per user, plus optional per-project activity channel `project-{id}`. Authorization on
connect; heartbeats; JSON protocol `{type, event, payload}`.

## 7. Background work

Celery with Redis broker. Duties: webhook delivery with exponential backoff + jitter,
notification fan-out (email + in-app), RFI/submittal overdue sweeps, invoice/retention
reminders, forecast rollups, document virus-scan hook (placeholder for external scanner),
export generation. All tasks are idempotent where re-delivery is possible.

## 8. Financials integrity

- All money fields: `DecimalField(max_digits=14, decimal_places=2)`; quantities/rates
  `max_digits=12, decimal_places=4` where needed.
- Budget changes, commitment changes, PO/invoice posting, change order approvals run
  inside `transaction.atomic()` with `select_for_update()` on the parent budget/commitment.
- Change orders move through draft → pending → approved/rejected; approval posts amounts
  to the budget (original/revised cost) atomically and writes an audit event.
- Idempotency keys (`Idempotency-Key` header) are stored for POST endpoints that move
  money or trigger approval transitions.

## 9. Files

- `django-storages` backend switchable: S3 (`STORAGE_BACKEND=s3`) or local disk (dev).
- Documents/drawings/photos store object keys, size, content type, checksum; versions
  are immutable rows pointing at distinct objects.
- Downloads: authenticated streaming endpoint that re-checks project permission and
  logs an audit event; optional short-lived signed URL for `<img>` display.

## 10. API surface (all under `/api/v1/`)

- `auth/` — login, refresh, logout, MFA enroll/verify/disable, me, password change/reset
- `organizations/`, `memberships/`, `roles/`, `invitations/`
- `projects/`, `project-members/`, `milestones/`, `activity/`
- `documents/`, `document-versions/`, `drawings/`, `drawing-revisions/`, drawing reviews
- `daily-logs/` (+ nested labour/weather/equipment/photos), `observations/`
- `tasks/`, `task-dependencies/`
- `rfis/` (+comments), `submittals/` (+items, approvals)
- `cost-codes/`, `budgets/`, `commitments/`, `purchase-orders/`, `invoices/`, `change-orders/`, `forecasts/`
- `inspections/`, `defects/`, `punch-lists/`, `safety-incidents/`, `corrective-actions/`
- `reports/`, `analytics/`, `exports/`
- `notifications/`, `webhooks/`, `api-applications/`, `integrations/health/`
- `admin/` — users, org settings, audit log, feature flags, ops metrics
- `dashboard/` — cross-project KPIs for the active org
- OpenAPI via `drf-spectacular` at `/api/schema/` + Swagger UI at `/api/docs/`

## 11. Frontend (Angular, standalone components)

```
frontend/src/app/
  core/        # interceptors (JWT, X-Organization-Id), guards, auth service,
               # notification socket service, error handler
  shared/      # UI kit: spinner, empty state, confirm dialog, money/date pipes,
               # typed model classes, table/pagination components
  layout/      # app shell: sidebar, topbar, project switcher, notification tray
  features/
    auth/            login, MFA challenge, password reset, profile
    dashboard/       org + project dashboards (KPIs, charts, activity)
    projects/        list/create/settings/team/milestones
    documents/       library, upload, version history, drawing set + revision compare
    field/           daily logs, photos, observations
    tasks/           board + table + gantt-lite schedule
    rfis/            RFI + submittal tracking, approval actions
    financials/      budget tables, cost codes, commitments, POs, invoices, change orders
    quality/         inspections, punch lists, defects, safety
    reports/         analytics + exports
    integrations/    API keys, webhooks, delivery logs
    admin/           users, org settings, audit log, feature settings
```

State: services + RxJS signals; no NgRx (kept deliberately lean). Typed API client per
domain with a shared `ApiService`. Route guards: `authGuard`, `orgGuard`, `projectGuard`,
`permissionGuard`. Responsive layout with CSS grid/flex; accessible forms (ARIA),
loading/empty/error states everywhere, confirm dialogs for destructive actions.

## 12. Testing strategy

- Backend: `pytest` + `pytest-django`. Factories in `common/testing.py`. Coverage of
  auth flows, permission/tenancy isolation (cross-org access must 404/403), financial
  transaction logic, webhook signing/retries, idempotency, approvals.
- Tests run against SQLite by default when `DATABASE_URL` is unset (developer laptops/CI
  without services) and against PostgreSQL when provided (Docker CI). Models avoid
  Postgres-only features so parity holds.
- Frontend: Jasmine/Karma unit tests for services/guards and a couple of components;
  `ng build` is part of the verification gate.

## 13. Ops

- Health endpoints: `/api/v1/health/` (liveness), `/api/v1/health/ready/` (DB + Redis + storage).
- Structured JSON logging with request ids; Sentry hook stub activated when `SENTRY_DSN` set.
- Backups: `docs/BACKUPS.md` documents `pg_dump` cron + S3 versioning/replication guidance.
- Migrations run on container start (opt-out via `RUN_MIGRATIONS=0`).
- Seed: `python manage.py seed_dev_data` creates synthetic orgs, users, projects and
  sample records across every module. Never uses real financial or customer data.

## 14. Security notes

- Secrets only via environment (`.env` never committed; `.env.example` documents all keys).
- CORS/CSRF tuned for the SPA origin; JWT rotation + reuse detection; OAuth scopes limited.
- Webhook outbound HMAC-SHA256 signatures (`X-SiteForge-Signature`) with timestamp
  tolerance; deliveries retried ≤5 times with exponential backoff; duplicate event ids
  rejected via unique delivery/event keys.
- Upload validation: extension + content-type allowlist, size limits, non-executable storage keys.
