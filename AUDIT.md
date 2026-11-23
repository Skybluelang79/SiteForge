# SiteForge Stack Audit

Date: 2026-11-20

## Verification baseline

- Backend: `python -m pytest -q` — 27 passed when `DJANGO_TEST=1` and `DJANGO_SECRET_KEY` are set.
  - Without those variables the suite fails at collection/readiness: `DJANGO_SECRET_KEY` is required in non-debug mode, and readiness returns 503 because Redis is unavailable.
  - Test dependencies `pytest-django`, `pytest-env`, and `factory-boy` were not declared in `requirements.txt`.
- Frontend: `npm run build` — succeeds; initial bundle 299.79 kB raw / 82.13 kB transfer.
- Frontend: `npm test` — not runnable; no test target, specs, or Karma/Vitest config.
- CI: no `.github/workflows` present.

## Current verification (2026-11-20)

- Backend: `python -m pytest -q` — 37 passed.
- Frontend: `npm run build` — succeeds; initial bundle 303.70 kB raw / 82.88 kB transfer.
- Frontend: `npm test -- --watch=false` — 2 test files, 3 tests passed.
- User API login and Django admin login are covered by `backend/tests/test_login_access.py`.
- Cloudflare integrations are implemented but disabled until real Turnstile/Access credentials are configured.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.14, Django 6.1, DRF, drf-spectacular, SimpleJWT, OAuth2 toolkit, django-otp |
| Data | PostgreSQL (SQLite fallback), Redis cache/channels, Celery worker + beat |
| Async | Django Channels/WebSockets at `/ws/notifications/` |
| Storage | Local filesystem or S3-compatible via django-storages |
| Frontend | Angular 22 standalone, zoneless, signals, Chart.js, three.js |
| Deploy | Docker Compose (full stack), Fly.io (app/worker/beat), Vercel (SPA), Render (web only) |

## Implemented

Backend apps: `accounts`, `organizations`, `projects`, `documents`, `drawings`, `field`, `tasks`, `rfis`, `financials`, `quality`, `reports`, `integrations`, `notifications`, `ads`, `assistant`, `audit`, `seed`.

Cross-cutting: UUID models with timestamps/soft delete, org/project-scoped permissions, request IDs, idempotency keys, structured JSON logs, throttles, health/readiness, audit events, webhook signing and retries, report exports, metric snapshots, MFA, session revocation, seeded demo data.

Frontend: dashboard, projects, resource lists, task board, financial workspace, field/RFI/submittal/punch-list details, notifications, assistant, command palette, profile/MFA, organization invitations, ad slots, client-only design canvas.

## Gaps

### P0 — production blockers

1. No CI/CD: no automated pytest, migration check, schema check, or frontend build.
2. Frontend test harness absent; `npm test` has no target.
3. Test dependencies undeclared; bare `pytest` fails without env setup.
4. Deployment drift: `render.yaml` has only a web service, so Celery jobs never run there; Python version differs between README (3.12+) and Docker/Render (3.14).
5. Config drift: duplicate AI settings in `backend/config/settings.py` (later block wins); `SENTRY_DSN` configured without `sentry-sdk` installed.
6. Security: tokens in `localStorage`, legacy WebSocket token query auth, permissive ad iframe sandbox, no CSP header.

### P1 — functional gaps

1. Design canvas is client-only; no save/load API.
2. No forgot-password/reset UI despite backend endpoints.
3. No org feature-flag UI despite `organizations/{id}/features/`.
4. Most backend custom actions (RFI respond/approve/close, quality signoff/resolve/verify, financial approve/issue/lock, report download) are not exposed in the UI.
5. No admin console UI; OpenAPI advertises an `admin` tag that has no API.

### P2 — operability and polish

1. No metrics/tracing/alerting; backups documented but not automated.
2. Docs drift: PDF export and virus scanning claimed but unimplemented; ads app undocumented.
3. Dependencies are lower-bound ranges, not locked.
4. Duplicate `command-palette` and `site-plan` component sets.

## Recommended roadmap

- **P0:** CI pipeline; declared test deps + deterministic pytest env; frontend tests; unify deploy targets and Python version; dedupe config; add CSP, tighten WebSocket auth and iframe sandbox.
- **P1:** persistent canvas API/UI; password-reset flow; feature-flag UI; surface backend actions.
- **P2:** observability and backup automation; webhook delivery UI; realtime project channels; PDF/XLSX and scheduled reports.

## Current product gap analysis (2026-11-20)

### Now present

- Cloudflare-backed register/login with Turnstile challenge, Cloudflare Access/Zero Trust assertion support, and a Worker proxy for `/api/*` and `/ws/*`.
- Professional canvas signup/login UI with static HTML5 canvas visuals; the 2D animated scene remains untouched.
- Reusable AI "Project Intelligence" panel on dashboard and project detail, using the existing assistant API.
- Operations Center at `/operations` with KPI tiles, project filter, and real data for schedule, commercial, quality/safety, documents/drawings, and field activity.
- Design Canvas "Auth-flow mockup" generator that creates a saveable board showing credentials → verification → workspace.
- Explicit tests for user API login and Django admin login.

### Highest-value inputs still missing

| Area | Current state | Recommended input | Priority |
| --- | --- | --- | --- |
| In-app admin console | Django admin works; no staff-only SPA console | Add `/admin` panel for users, orgs, plans, feature flags, audit log, webhooks, and impersonation with strict RBAC | P1 |
| Session security | Access/refresh tokens in `localStorage` | Move to httpOnly, Secure, SameSite cookies with CSRF protection | P0 |
| Cloudflare rollout | Code and docs complete; secrets not configured | Add Turnstile keys, Access team domain/AUD, deploy Worker, set runtime site key | P0 |
| Observability | Structured logs only | Sentry + OpenTelemetry traces, uptime checks, alert routing, request/latency dashboards | P0 |
| Backups | Documented, not automated | Scheduled DB/media backups, retention policy, restore drill, backup health check | P0 |
| Exports | CSV/report jobs; no PDF/XLSX | Branded PDF/XLSX templates, scheduled email reports, export history preview | P1 |
| Realtime | WebSocket endpoint exists; no project channels | Live task, RFI, document, and safety channels with presence and unread state | P1 |
| Webhooks | Signing/retries exist; no delivery UI | Delivery log, payload inspection, manual resend, endpoint health | P1 |
| Schedule | Timeline view in Operations Center | True Gantt with dependencies, baselines, critical path, resource leveling | P1 |
| Drawings/documents | Registers and versions only | Versioned drawing register with markup, layers, transmittals, RFI links | P1 |
| BIM/3D | No model support | Model viewer with issue pinning, model/document cross-references | P2 |
| Field operations | Daily logs, incidents, punch lists | Geotagged photos, QR/barcode assets, offline mobile sync, toolbox talks, equipment telemetry | P2 |
| Commercial control | Commitments/invoices lists | Bids/tenders, change orders, payment applications, budget-vs-actual analytics | P1 |
| Compliance | No permits/insurance/inspections | Permit register, insurance expiry alerts, inspection checklist, certificate repository | P1 |
| Closeout | Punch lists only | Signoff workflows, warranties, O&M manuals, as-built handover | P2 |
| Integrations | Webhooks + OAuth2 toolkit | Email/calendar sync and connectors for Procore, Autodesk, QuickBooks, and Slack/Teams | P2 |
| AI | Generic provider-backed chat panel | Project-trained context, document/RFI risk analysis, automated status briefing drafts, action item extraction | P1 |
| Sustainability | None | LEED/energy tracking, waste logs, carbon reporting | P2 |

### Suggested next implementation batch

1. Configure Cloudflare credentials and deploy the Worker; migrate tokens to cookies.
2. Add observability and automated backups with restore testing.
3. Build the in-app admin console and webhook delivery UI.
4. Replace the Operations Center timeline with a dependency-aware schedule module.
5. Add branded PDF/XLSX exports and scheduled reports.
6. Add drawing markup, permits/insurance compliance, and closeout workflows.

## Remediation status (2026-11-20)

### Done

- Added `.github/workflows/ci.yml` running Django checks, migration drift, OpenAPI schema, pytest, frontend build, and Vitest.
- Declared `pytest-env` in `backend/requirements-dev.txt`; `pytest.ini` now supplies test-only env values, so bare `pytest` passes 37 tests.
- Added Angular `@angular/build:unit-test` target, `tsconfig.spec.json`, Vitest/jsdom, and smoke tests for `API_ROOT` and `RESOURCE_PAGES`.
- Deduplicated AI settings, aligned README to Python 3.14, added `sentry-sdk`, removed the misleading OpenAPI `admin` tag.
- Added Render `worker` and `beat` services; added CSP/Referrer-Policy/Permissions-Policy headers, removed legacy WebSocket token query auth, tightened the ad iframe sandbox.
- Added persistent `CanvasBoard` API and save/load UI; forgot-password/reset-password flow; org feature-flag editor; action buttons for RFI, quality, financial, and export-job workflows.
- Added Cloudflare Turnstile and Access backend verification, auth endpoints, frontend integration, Worker proxy, Wrangler config, and setup docs.
- Added professional signup/login canvas UI, Design Canvas auth-flow mockup generator, and login tests for both the user API and Django admin.
- Added reusable AI "Project Intelligence" panel to dashboard and project detail, plus an Operations Center `/operations` page with real project data.

### Still open

- Access/refresh tokens remain in `localStorage`; migrating to httpOnly cookies is a larger auth redesign.
- Cloudflare credentials/runtime site key and Worker deployment are not configured yet.
- No in-app admin console UI, metrics/tracing/alerting, backup automation, webhook delivery UI, or realtime project channels.
- PDF/XLSX exports, scheduled reports, true Gantt scheduling, drawing markup, BIM/3D, offline mobile sync, compliance, and closeout workflows are not implemented.
- Docs still claim virus scanning and PDF export; stale untracked `_pytest_*.txt` artifacts were removed.
