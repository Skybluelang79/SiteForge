# Cloudflare Worker (SiteForge edge)

`cloudflare/worker.js` fronts `/api/*` and `/ws/*` on the Worker host. It forwards `Authorization`,
`X-Organization-Id`, `Idempotency-Key`, cookies and `CF-Access-Jwt-Assertion` to `ORIGIN`, answers CORS
preflights with `ALLOWED_ORIGIN`, adds security headers, and serves `GET /health`.

## Turnstile keys

1. In Cloudflare dashboard → Turnstile, create a widget for the frontend host; copy the **Site Key**
   (public) and **Secret Key** (private).
2. Store the Secret Key as a Worker secret:

   ```sh
   cd cloudflare
   wrangler secret put TURNSTILE_SECRET_KEY
   ```

   When this secret is unset the Worker does not require a token. When it is set, POST
   `/api/v1/auth/login/` and `/api/v1/auth/register/` must supply a token via the
   `cf-turnstile-response` header or `turnstile_token` in the JSON body; the Worker calls
   `https://challenges.cloudflare.com/turnstile/v0/siteverify` and returns HTTP 400 before proxying if
   verification fails (missing token, failed check, or siteverify error).
3. Inject the public Site Key into the frontend at build time via `TURNSTILE_SITE_KEY`. Have the
   runtime-config generation step (`frontend/scripts/write-runtime-config.js`) emit it as
   `window.__sf.turnstileSiteKey`, which `TurnstileService` uses to render the widget;
   `AuthService.login()` sends the resulting token as `turnstile_token`:

   ```sh
   TURNSTILE_SITE_KEY="0x..." \
   SITEFORGE_API_ROOT="https://<worker-host>/api/v1" \
   SITEFORGE_WS_BASE="wss://<worker-host>" \
   npm run vercel-build
   ```

   Cloudflare Access is independent of Turnstile and stays hidden in the SPA unless
   `CLOUDFLARE_ACCESS_ENABLED=true` is also set during the frontend build.

## Cloudflare Access

1. In Cloudflare dashboard → Access → Applications, add an application for the Worker host. Note the
   **team domain** (`https://<team>.cloudflareaccess.com`) used for the login redirect and the
   application **Audience tag (AUD)**.
2. Store the audience as a Worker secret:

   ```sh
   wrangler secret put CLOUDFLARE_ACCESS_AUD
   ```

3. The Worker passes `CF-Access-Jwt-Assertion` through to the Django backend, which uses the configured
   audience when validating Access-issued assertions for
   `POST /api/v1/auth/cloudflare-access/`. Use `withCredentials: true` on that frontend call. Ensure
   `CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS` on the backend include the frontend origin
   (and the Worker host if it is called directly).

## Deploy

1. Install/login: `npm install -g wrangler && wrangler login`.
2. Edit `cloudflare/wrangler.toml`: set `ORIGIN` to the Django backend base URL (no trailing slash)
   and `ALLOWED_ORIGIN` to the frontend origin. Secrets above are set with `wrangler secret put`.
3. Deploy: `cd cloudflare && wrangler deploy` (or `wrangler deploy --config cloudflare/wrangler.toml`).
4. Attach a route/custom domain for the Worker in the Cloudflare dashboard, then point the frontend at
   it (`SITEFORGE_API_ROOT=https://<worker-host>/api/v1`, `SITEFORGE_WS_BASE=wss://<worker-host>`).
5. Verify: `curl https://<worker-host>/health` returns `{"status":"ok","service":"siteforge-edge"}`;
   use `wrangler tail` to inspect proxied requests.
