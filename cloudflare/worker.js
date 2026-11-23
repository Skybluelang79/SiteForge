const SECURITY_HEADERS = {
  "Content-Security-Policy": "default-src 'self'; base-uri 'self'; object-src 'none'; form-action 'self'; frame-ancestors 'none'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' ws: wss:; frame-src 'self' https://challenges.cloudflare.com https:",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
};

const ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS";
const ALLOWED_REQUEST_HEADERS = [
  "Authorization",
  "Content-Type",
  "X-Organization-Id",
  "Idempotency-Key",
  "Cookie",
  "CF-Access-Jwt-Assertion",
  "cf-turnstile-response",
  "X-Requested-With",
];
const PRESERVED_HEADERS = [
  "authorization",
  "x-organization-id",
  "idempotency-key",
  "cookie",
  "cf-access-jwt-assertion",
];
const TURNSTILE_PATHS = new Set(["/api/v1/auth/login/", "/api/v1/auth/register/"]);
const SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

function jsonResponse(payload, status) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function applyHeaders(response, env) {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    headers.set(name, value);
  }
  if (env.ALLOWED_ORIGIN) {
    headers.set("Access-Control-Allow-Origin", env.ALLOWED_ORIGIN);
    headers.set("Access-Control-Allow-Credentials", "true");
    const vary = headers.get("Vary");
    if (!vary) {
      headers.set("Vary", "Origin");
    } else if (!vary.split(",").some((item) => item.trim().toLowerCase() === "origin")) {
      headers.set("Vary", `${vary}, Origin`);
    }
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function preflightResponse(request, env) {
  const headers = new Headers();
  if (env.ALLOWED_ORIGIN) {
    headers.set("Access-Control-Allow-Origin", env.ALLOWED_ORIGIN);
  }
  headers.set("Access-Control-Allow-Methods", ALLOWED_METHODS);
  const allowHeaders = new Set(ALLOWED_REQUEST_HEADERS.map((name) => name.toLowerCase()));
  const requested = request.headers.get("Access-Control-Request-Headers");
  if (requested) {
    for (const name of requested.split(",")) {
      const trimmed = name.trim().toLowerCase();
      if (trimmed) {
        allowHeaders.add(trimmed);
      }
    }
  }
  headers.set("Access-Control-Allow-Headers", [...allowHeaders].join(", "));
  headers.set("Access-Control-Allow-Credentials", "true");
  headers.set("Access-Control-Max-Age", "86400");
  headers.set("Vary", "Origin");
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    headers.set(name, value);
  }
  return new Response(null, { status: 204, headers });
}

function targetUrl(request, origin) {
  const target = new URL(origin);
  const source = new URL(request.url);
  const base = target.pathname.replace(/\/$/, "");
  target.pathname = `${base}${source.pathname}`;
  target.search = source.search;
  return target;
}

function forwardedHeaders(request) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  for (const name of PRESERVED_HEADERS) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
  return headers;
}

function upstreamRequest(request, target, body) {
  const init = {
    method: request.method,
    headers: forwardedHeaders(request),
    redirect: "manual",
  };
  if (body !== undefined) {
    init.body = body;
  } else if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }
  return new Request(target.toString(), init);
}

async function verifyTurnstile(request, env, bodyText) {
  let token = request.headers.get("cf-turnstile-response");
  if (!token && bodyText) {
    try {
      const payload = JSON.parse(bodyText);
      if (payload && typeof payload.turnstile_token === "string") {
        token = payload.turnstile_token;
      }
    } catch {
      token = "";
    }
  }
  if (!token) {
    return false;
  }
  const form = new URLSearchParams({ secret: env.TURNSTILE_SECRET_KEY, response: token });
  const clientIp = request.headers.get("CF-Connecting-IP");
  if (clientIp) {
    form.set("remoteip", clientIp);
  }
  try {
    const response = await fetch(SITEVERIFY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!response.ok) {
      return false;
    }
    const result = await response.json();
    return Boolean(result && result.success === true);
  } catch {
    return false;
  }
}

function turnstileError() {
  return jsonResponse(
    { error: { code: "turnstile_failed", message: "Turnstile verification failed.", details: {} } },
    400,
  );
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;

    if (request.method === "OPTIONS" && request.headers.has("Access-Control-Request-Method")) {
      return preflightResponse(request, env);
    }

    if (path === "/health") {
      return applyHeaders(jsonResponse({ status: "ok", service: "siteforge-edge" }, 200), env);
    }

    if (!path.startsWith("/api/") && !path.startsWith("/ws/")) {
      return applyHeaders(
        jsonResponse({ error: { code: "not_found", message: "Not found.", details: {} } }, 404),
        env,
      );
    }

    if (!env.ORIGIN) {
      return applyHeaders(
        jsonResponse(
          { error: { code: "misconfigured", message: "ORIGIN is not configured.", details: {} } },
          503,
        ),
        env,
      );
    }

    const target = targetUrl(request, env.ORIGIN);

    if (path.startsWith("/ws/")) {
      return fetch(upstreamRequest(request, target));
    }

    let bodyText;
    if (env.TURNSTILE_SECRET_KEY && request.method === "POST" && TURNSTILE_PATHS.has(path)) {
      bodyText = await request.text();
      if (!(await verifyTurnstile(request, env, bodyText))) {
        return applyHeaders(turnstileError(), env);
      }
    }

    const response = await fetch(upstreamRequest(request, target, bodyText));
    return applyHeaders(response, env);
  },
};
