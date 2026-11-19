# Deployment (Vercel frontend + Fly.io backend)

## Architecture
- **Frontend**: Angular SPA in `frontend/` (build output `dist/siteforge-web/browser`) — deploy to Vercel.
- **Backend**: Django + Daphne ASGI in `backend/` — deploy to Fly.io (Postgres + Redis required for production features).

## Backend on Fly.io

1. Install Fly CLI and log in: `fly auth login`
2. From `backend/`:
   - Create app (first time): `fly launch --no-deploy` (use existing `fly.toml` or adjust `app` name/region)
   - Create Postgres and attach: `fly postgres create` then `fly postgres attach <pg-app>` (sets `DATABASE_URL`)
   - Provision Redis (Upstash or `fly redis create`) and set `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
3. Set secrets/env (replace values):
   ```sh
   fly secrets set DJANGO_SECRET_KEY="<long-random>" \
      DJANGO_DEBUG=False \
      DJANGO_TRUST_PROXY_HEADERS=True \
      DJANGO_ALLOWED_HOSTS="<app>.fly.dev" \

     CORS_ALLOWED_ORIGINS="https://<your-vercel-app>.vercel.app" \
     DJANGO_CSRF_TRUSTED_ORIGINS="https://<your-vercel-app>.vercel.app" \
     FRONTEND_URL="https://<your-vercel-app>.vercel.app" \
     SITE_URL="https://<app>.fly.dev"
   ```
4. Deploy: `fly deploy`
5. (Optional) Seed demo data once: `fly ssh console -C "python manage.py seed_dev_data --reset"` and/or create an admin: `fly ssh console -C "python manage.py createsuperuser"`
6. Verify: `https://<app>.fly.dev/api/v1/health/ready/` and `/admin/`

Notes: entrypoint runs `migrate` and `collectstatic` on start. `fly.toml` defines the `app`, `worker` and `beat` processes; deploy all three (`fly deploy`) and keep at least one app machine running for WebSockets. Set `WEBHOOK_ALLOW_PRIVATE_TARGETS=True` only if you intentionally deliver to private endpoints. Media uploads use local storage by default (ephemeral on Fly) — configure S3 (`STORAGE_BACKEND=s3`, `AWS_*`) for persistence.


## Frontend on Vercel

1. Import the repo in Vercel and set **Root Directory** to `frontend` (or configure accordingly).
2. Build settings (also in `frontend/vercel.json`): build `npm run vercel-build`, output `dist/siteforge-web/browser`. SPA rewrites are configured.
3. Set environment variables for the production build so the app calls your Fly backend:
   - `SITEFORGE_API_ROOT=https://<app>.fly.dev/api/v1`
   - `SITEFORGE_WS_BASE=wss://<app>.fly.dev`
4. Deploy. After deploy, ensure backend `CORS_ALLOWED_ORIGINS`/`DJANGO_CSRF_TRUSTED_ORIGINS` include your Vercel domain (and preview domains if desired).

## Local dev
- Frontend dev server proxies `/api` and `/ws` to `http://localhost:8000` (`frontend/proxy.conf.json`), and `assets/runtime-config.js` defaults to same-origin `/api/v1`.
- Backend: run from `backend/` with `../.venv/Scripts/python.exe manage.py runserver` (see root README).
