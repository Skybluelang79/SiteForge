# SiteForge conventions

## Models

- Every domain model inherits `apps.common.models.Base` (UUID primary key, `created_at`,
  `updated_at`).
- Soft-deletable aggregates (`Organization`, `Project`) use `deleted_at` and managers that exclude
  deleted rows. Never use an invented `is_deleted` field in queries.
- Money uses `MoneyField`/`DecimalField(max_digits=14, decimal_places=2)`. Never use floats.
- Add explicit `related_name`, indexes for common project/status filters, and unique constraints
  scoped to the owning project or organization.
- Choices stay as class-level `*_CHOICES` lists on the model.

## Serializers

- `ModelSerializer` by default; nested user references use `UserSummarySerializer`.
- Write-only UUID conveniences are suffixed `_id` (for example `assignee_id`), popped in the
  viewset's `perform_create`/`perform_update`, and never echoed back.
- Computed values (`variance`, `open_balance`, `has_credentials`) are read-only serializer fields
  or model properties.
- Validation that spans fields lives in `validate()`; single-field checks use `validate_<field>`.

## ViewSets and permissions

- `OrgScopedViewSet` for organization-owned records; `ProjectScopedViewSet` for records reached
  through `project` (org scoping is derived from `project__organization_id`).
- Declare `action_permissions` with permission keys from `apps.common.permissions`:

```python
action_permissions = {
    "read": ("tasks.view",),
    "create": ("tasks.create",),
    "update": ("tasks.edit",),
    "destroy": ("tasks.delete",),
    "write": ("tasks.create",),
}
```

- Use `http_method_names = ["get", "head", "options"]` for genuinely read-only viewsets instead of
  MRO gymnastics.
- Set `project` on create from the active project in the client; enforce project access with
  `user.can_access_project(project)` inside `perform_create`.
- Audit sensitive mutations with:

```python
record_audit_event(
    organization=obj.project.organization,  # object, not organization_id
    actor=self.request.user,
    action="thing.created",
    target_type="Thing",
    target_id=obj.id,
    project=obj.project,
    request=self.request,
)
```

## Filtering and pagination

- All list endpoints use `StandardPagination` (25 per page, `page_size` up to 200), returning
  `{count, next, previous, results}`.
- Use `DjangoFilterBackend`, `SearchFilter` and `OrderingFilter` via the common viewsets.
- Project-scoped endpoints accept `?project=<uuid>` (and `?project_id=`).

## Background jobs and notifications

- Celery tasks live in `<app>/tasks.py`; schedule entries go in `CELERY_BEAT_SCHEDULE`.
- Notifications are created through `apps.notifications.services.notify`; websocket fan-out is
  best-effort and must never break the write path.
- Webhooks are signed with HMAC-SHA256 using the subscription secret and retried with backoff.

## Tests

- Cross-app workflow tests live in `backend/tests/`; app-specific tests may live next to apps.
- Use `apps.common.testing.build_org_with_owner`, `authenticated_client` and `create_project`.
- Prefer API-level tests (`APIClient`) for permissions and workflows; use model-level tests for
  invariant helpers.
- Run `pytest -q --no-header` from `backend/`. Keep `manage.py check` and
  `makemigrations --check --dry-run` clean.

## Frontend

- Standalone components, `ChangeDetectionStrategy.OnPush`, signal-based state.
- All HTTP goes through `ApiService`; auth headers (`Authorization`, `X-Organization-Id`) are added
  by `authInterceptor`.
- Route-level lazy loading for feature areas. Keep visual language consistent with the existing
  tokens (navy `#0f172a`, amber `#f59e0b`, slate greys).
