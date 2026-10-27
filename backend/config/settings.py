"""Django settings for the SiteForge platform.

All secrets are supplied through environment variables (see .env.example).
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, True),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "backend"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:4200", "http://127.0.0.1:4200"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:4200", "http://127.0.0.1:4200"]),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
    CELERY_TASK_EAGER_PROPAGATES=(bool, True),
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    STORAGE_BACKEND=(str, "local"),
)

# Read .env if present (never commit the real file).
environ.Env.read_env(BASE_DIR / ".env")

# Resolve the database engine once. PostgreSQL is used when DATABASE_URL is
# configured; otherwise we fall back to SQLite so tests and laptops work
# without any external services (see ARCHITECTURE.md §12).
if env("DB_ENGINE", default=""):
    DB_ENGINE = env("DB_ENGINE")
elif env("DATABASE_URL", default=""):
    DB_ENGINE = "postgresql"
else:
    DB_ENGINE = "sqlite3"

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres" if DB_ENGINE == "postgresql" else None,
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "oauth2_provider",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "channels",
    "storages",
    # First-party
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.projects",
    "apps.documents",
    "apps.drawings",
    "apps.field",
    "apps.tasks",
    "apps.rfis",
    "apps.financials",
    "apps.quality",
    "apps.reports",
    "apps.integrations",
    "apps.notifications",
    "apps.audit",
    "seed",
]
INSTALLED_APPS = [a for a in INSTALLED_APPS if a]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.common.middleware.RequestIdMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.common.idempotency.IdempotencyMiddleware",
    "apps.organizations.middleware.ActiveOrganizationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL in Docker/production; SQLite fallback for local tests
# ---------------------------------------------------------------------------
if DB_ENGINE == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", default=str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL",
            default=f"postgresql://{env('POSTGRES_USER', default='siteforge')}:"
            f"{env('POSTGRES_PASSWORD', default='siteforge')}@"
            f"{env('POSTGRES_HOST', default='localhost')}:"
            f"{env('POSTGRES_PORT', default='5432')}/"
            f"{env('POSTGRES_DB', default='siteforge')}",
        )
    }

CONN_MAX_AGE = env.int("DB_CONN_MAX_AGE", default=60)

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Storage — local disk for dev, S3-compatible for production
# ---------------------------------------------------------------------------
STORAGES = {
    "default": {
        "BACKEND": (
            "storages.backends.s3boto3.S3Boto3Storage"
            if env("STORAGE_BACKEND") == "s3"
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_S3_FILE_OVERWRITE = False

# Upload limits
MAX_UPLOAD_SIZE = env.int("MAX_UPLOAD_SIZE", default=50 * 1024 * 1024)  # 50 MB
ALLOWED_UPLOAD_EXTENSIONS = env.list(
    "ALLOWED_UPLOAD_EXTENSIONS",
    default=[
        "pdf", "png", "jpg", "jpeg", "gif", "webp", "svg",
        "doc", "docx", "xls", "xlsx", "csv", "txt", "dwg", "dxf", "zip",
    ],
)

# ---------------------------------------------------------------------------
# Redis / Channels / Celery
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}
if env.bool("USE_IN_MEMORY_CHANNEL_LAYER", default=False) or env("DJANGO_TEST", default="") == "1":
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = env("CELERY_TASK_EAGER_PROPAGATES")
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=300)
CELERY_BEAT_SCHEDULE = {
    "sweep-due-dates-hourly": {
        "task": "apps.rfis.tasks.sweep_due_dates",
        "schedule": 3600.0,
    },
    "daily-metrics": {
        "task": "apps.reports.tasks.collect_daily_metrics",
        "schedule": 6 * 3600.0,
    },
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "oauth2_provider.backends.OAuth2Backend",
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

OAUTH2_PROVIDER = {
    "SCOPES": {
        "read": "Read access",
        "write": "Write access",
        "projects": "Project data",
        "financials": "Financial data",
        "webhooks": "Manage webhooks",
    },
    "PKCE_REQUIRED": True,
}

# django-otp
OTP_TOTP_SYNC_ISSUER = True
SITE_NAME = "SiteForge"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": f"{env.int('THROTTLE_ANON', default=60)}/min",
        "user": f"{env.int('THROTTLE_USER', default=600)}/min",
        "auth": "20/min",
        "uploads": "60/min",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SiteForge API",
    "DESCRIPTION": "Enterprise construction management platform API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "TAGS": [
        {"name": "auth", "description": "Authentication and MFA"},
        {"name": "organizations", "description": "Organizations, memberships, roles, invitations"},
        {"name": "projects", "description": "Projects, teams, milestones, activity"},
        {"name": "documents", "description": "Documents and drawings"},
        {"name": "field", "description": "Daily logs, labour, weather, photos, observations"},
        {"name": "tasks", "description": "Task management and scheduling"},
        {"name": "rfis", "description": "RFIs and submittals"},
        {"name": "financials", "description": "Budgets, commitments, invoices, change orders"},
        {"name": "quality", "description": "Inspections, defects, punch lists, safety"},
        {"name": "reports", "description": "Reports, analytics, exports"},
        {"name": "integrations", "description": "API credentials, webhooks, OAuth apps"},
        {"name": "notifications", "description": "User notifications"},
        {"name": "admin", "description": "Administrative console"},
        {"name": "dashboard", "description": "Dashboards"},
    ],
}

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@siteforge.local")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)

# ---------------------------------------------------------------------------
# Logging — structured JSON in production, readable console in dev
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.common.logging.JsonLogFormatter"},
        "simple": {"format": "{levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "json",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "apps": {"level": LOG_LEVEL, "propagate": True},
        "django.request": {"level": "WARNING", "propagate": True},
    },
}

# ---------------------------------------------------------------------------
# Sentry (optional — activates only when DSN provided)
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN and not DEBUG:  # pragma: no cover
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05)
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Platform-specific tunables
# ---------------------------------------------------------------------------
SITE_URL = env("SITE_URL", default="http://localhost:8000")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:4200")
WEBHOOK_MAX_RETRIES = env.int("WEBHOOK_MAX_RETRIES", default=5)
WEBHOOK_TIMEOUT_SECONDS = env.int("WEBHOOK_TIMEOUT_SECONDS", default=10)
DOWNLOAD_URL_TTL_SECONDS = env.int("DOWNLOAD_URL_TTL_SECONDS", default=300)
DEFAULT_ORG_ROLE = "member"
