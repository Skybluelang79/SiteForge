"""Platform permission keys and role matrix.

Permission keys are strings like "projects.view", "financials.approve_change_order".
Roles map to sets of keys. Organization admins always retain full access; the
matrix defines what lower roles may do. Project members can additionally be
limited per-project through ProjectMember.role.
"""

# Permission key catalog, grouped by domain.
PERMISSIONS = {
    # organizations
    "org.view": "View organization profile",
    "org.edit": "Edit organization settings",
    "org.members.manage": "Invite/remove members and change roles",
    "org.roles.manage": "Manage custom roles",
    "org.audit.view": "View organization audit log",
    # projects
    "projects.view": "View projects",
    "projects.create": "Create projects",
    "projects.edit": "Edit project settings",
    "projects.delete": "Delete/archive projects",
    "projects.team.manage": "Manage project team",
    # documents / drawings
    "documents.view": "View documents",
    "documents.create": "Upload documents",
    "documents.edit": "Edit document metadata",
    "documents.delete": "Delete documents",
    "drawings.view": "View drawings",
    "drawings.create": "Create drawings",
    "drawings.edit": "Edit drawings and revisions",
    "drawings.review": "Review/approve drawing revisions",
    # field
    "field.view": "View daily logs and field data",
    "field.create": "Create daily logs, photos, observations",
    "field.edit": "Edit field records",
    "field.approve": "Approve daily logs",
    # tasks
    "tasks.view": "View tasks and schedule",
    "tasks.create": "Create tasks",
    "tasks.edit": "Edit tasks",
    "tasks.delete": "Delete tasks",
    # rfis / submittals
    "rfis.view": "View RFIs and submittals",
    "rfis.create": "Create RFIs and submittals",
    "rfis.edit": "Edit RFIs and submittals",
    "rfis.respond": "Respond to RFIs / review submittals",
    "rfis.approve": "Approve submittals and close RFIs",
    # financials
    "financials.view": "View financial data",
    "financials.create": "Create budgets, commitments, POs, invoices",
    "financials.edit": "Edit financial records",
    "financials.approve": "Approve change orders, invoices, POs",
    "financials.delete": "Delete draft financial records",
    # quality
    "quality.view": "View inspections, defects, punch lists, safety",
    "quality.create": "Create inspections, defects, punch items, incidents",
    "quality.edit": "Edit quality records",
    "quality.approve": "Sign off inspections and corrective actions",
    # reports
    "reports.view": "View reports and analytics",
    "reports.create": "Create/save report definitions",
    "reports.export": "Export report data",
    # integrations
    "integrations.view": "View integrations and webhooks",
    "integrations.manage": "Manage API apps, credentials, webhooks",
    # admin console
    "admin.users.manage": "Manage platform users",
    "admin.features.manage": "Manage feature settings",
    "admin.ops.view": "View operational metrics",
    # notifications
    "notifications.view": "View notifications",
}

VIEWER_PERMISSIONS = {
    "org.view",
    "projects.view",
    "documents.view",
    "drawings.view",
    "field.view",
    "tasks.view",
    "rfis.view",
    "financials.view",
    "quality.view",
    "reports.view",
    "notifications.view",
}

ENGINEER_PERMISSIONS = VIEWER_PERMISSIONS | {
    "projects.edit",
    "documents.create",
    "documents.edit",
    "drawings.create",
    "drawings.edit",
    "drawings.review",
    "field.create",
    "field.edit",
    "tasks.create",
    "tasks.edit",
    "rfis.create",
    "rfis.edit",
    "rfis.respond",
    "financials.create",
    "financials.edit",
    "quality.create",
    "quality.edit",
    "quality.approve",
    "reports.create",
    "reports.export",
}

CONTRACTOR_PERMISSIONS = VIEWER_PERMISSIONS | {
    "documents.create",
    "field.create",
    "field.edit",
    "tasks.create",
    "tasks.edit",
    "rfis.create",
    "financials.create",
    "quality.create",
    "quality.edit",
}

ADMIN_PERMISSIONS = set(PERMISSIONS.keys()) - {
    "admin.users.manage",  # platform-level only
}

OWNER_PERMISSIONS = set(PERMISSIONS.keys())

DEFAULT_ROLES = {
    "owner": OWNER_PERMISSIONS,
    "admin": ADMIN_PERMISSIONS,
    "member": ENGINEER_PERMISSIONS,
    "contractor": CONTRACTOR_PERMISSIONS,
    "viewer": VIEWER_PERMISSIONS,
}

ROLE_CHOICES = [(code, code.title()) for code in sorted(DEFAULT_ROLES)]


def permissions_for_role(role_code: str) -> set[str]:
    return set(DEFAULT_ROLES.get(role_code, set()))


def role_has_permission(role_code: str, key: str) -> bool:
    return key in permissions_for_role(role_code)
