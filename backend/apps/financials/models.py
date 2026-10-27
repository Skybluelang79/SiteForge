"""Financial management: budgets, cost codes, commitments, POs, invoices,
change orders, retention and forecasts.

All monetary values use 14-digit / 2-decimal precision. Mutations that move
money must run inside transaction.atomic() with row locks (see services.py).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.common.models import Base, MoneyField, RateField

User = get_user_model()


class CostCode(Base):
    """Hierarchical cost breakdown code."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="cost_codes")
    code = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["project", "code"], name="uniq_costcode_project_code")
        ]
        indexes = [models.Index(fields=["project", "is_active"], name="idx_costcode_project_active")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} - {self.name}"


class Budget(Base):
    STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("locked", "Locked"), ("archived", "Archived")]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="budgets")
    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    currency = models.CharField(max_length=3, default="USD")
    is_primary = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="budgets_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="budgets_created"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name", "version"], name="uniq_budget_project_name_version")
        ]
        indexes = [models.Index(fields=["project", "status"], name="idx_budget_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} v{self.version}"


class BudgetLine(Base):
    """A budgeted amount against a cost code within a budget."""

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="budget_lines", db_index=True
    )
    cost_code = models.ForeignKey(CostCode, on_delete=models.PROTECT, related_name="budget_lines")
    description = models.CharField(max_length=400, blank=True)
    budgeted_amount = MoneyField(default=0)
    committed_amount = MoneyField(default=0)
    actual_amount = MoneyField(default=0)
    forecast_amount = MoneyField(default=0)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost = RateField(default=0)

    class Meta:
        ordering = ["cost_code__code"]
        constraints = [
            models.UniqueConstraint(fields=["budget", "cost_code"], name="uniq_budgetline_budget_code")
        ]
        indexes = [
            models.Index(fields=["project", "cost_code"], name="idx_budgetline_project_code"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.budget_id}:{self.cost_code_id}"

    @property
    def variance(self):
        return self.budgeted_amount - self.actual_amount

    @property
    def remaining(self):
        return self.budgeted_amount - self.committed_amount - self.actual_amount


class Commitment(Base):
    """Umbrella for subcontracts / purchase orders issued to a vendor."""

    TYPE_CHOICES = [
        ("subcontract", "Subcontract"),
        ("purchase_order", "Purchase Order"),
        ("consultant", "Consultant"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("issued", "Issued"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="commitments")
    contract = models.ForeignKey(
        "projects.Contract", on_delete=models.SET_NULL, null=True, blank=True, related_name="commitments"
    )
    number = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=255)
    commitment_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default="subcontract", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    vendor_email = models.EmailField(blank=True)
    description = models.TextField(blank=True)
    original_amount = MoneyField(default=0)
    revised_amount = MoneyField(default=0)
    billed_amount = MoneyField(default=0)
    retention_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    currency = models.CharField(max_length=3, default="USD")
    issued_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="commitments_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="commitments_created"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_commitment_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_commitment_project_status"),
            models.Index(fields=["project", "commitment_type"], name="idx_commitment_project_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.number}: {self.title}"

    @property
    def retention_amount(self):
        return (self.revised_amount * self.retention_percent / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def open_balance(self):
        return self.revised_amount - self.billed_amount


class CommitmentLine(Base):
    commitment = models.ForeignKey(Commitment, on_delete=models.CASCADE, related_name="lines")
    cost_code = models.ForeignKey(CostCode, on_delete=models.PROTECT, related_name="commitment_lines")
    description = models.CharField(max_length=400, blank=True)
    amount = MoneyField(default=0)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost = RateField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["commitment", "cost_code"], name="uniq_commitmentline_commitment_code")
        ]
        indexes = [models.Index(fields=["commitment"], name="idx_commitmentline_commitment")]


class PurchaseOrder(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("issued", "Issued"),
        ("received", "Received"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="purchase_orders")
    commitment = models.ForeignKey(
        Commitment, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders"
    )
    number = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    vendor_reference = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    subtotal = MoneyField(default=0)
    tax_amount = MoneyField(default=0)
    shipping_amount = MoneyField(default=0)
    total_amount = MoneyField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    order_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders_approved"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders_created"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_po_project_number")
        ]
        indexes = [models.Index(fields=["project", "status"], name="idx_po_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return f"PO {self.number}"

    def save(self, *args, **kwargs):
        self.total_amount = (
            (self.subtotal or Decimal("0"))
            + (self.tax_amount or Decimal("0"))
            + (self.shipping_amount or Decimal("0"))
        )
        super().save(*args, **kwargs)


class PurchaseOrderLine(Base):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    cost_code = models.ForeignKey(
        CostCode, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_order_lines"
    )
    description = models.CharField(max_length=400)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost = RateField(default=0)
    line_total = MoneyField(default=0)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["purchase_order"], name="idx_poline_po")]

    def save(self, *args, **kwargs):
        self.line_total = ((self.quantity or Decimal("0")) * (self.unit_cost or Decimal("0"))).quantize(
            Decimal("0.01")
        )
        super().save(*args, **kwargs)


class Invoice(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("partially_paid", "Partially Paid"),
        ("disputed", "Disputed"),
        ("rejected", "Rejected"),
        ("void", "Void"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="invoices")
    commitment = models.ForeignKey(
        Commitment, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    number = models.CharField(max_length=60, db_index=True)
    vendor_invoice_number = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    subtotal = MoneyField(default=0)
    tax_amount = MoneyField(default=0)
    total_amount = MoneyField(default=0)
    retention_amount = MoneyField(default=0)
    net_payable = MoneyField(default=0)
    paid_amount = MoneyField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices_created"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_invoice_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_invoice_project_status"),
            models.Index(fields=["project", "due_date"], name="idx_invoice_project_due"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Invoice {self.number}"

    def recalculate(self):
        self.total_amount = ((self.subtotal or Decimal("0")) + (self.tax_amount or Decimal("0"))).quantize(
            Decimal("0.01")
        )
        self.net_payable = (self.total_amount - (self.retention_amount or Decimal("0"))).quantize(
            Decimal("0.01")
        )


class InvoiceLine(Base):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    cost_code = models.ForeignKey(
        CostCode, on_delete=models.PROTECT, null=True, blank=True, related_name="invoice_lines"
    )
    description = models.CharField(max_length=400)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost = RateField(default=0)
    line_total = MoneyField(default=0)
    scheduled_value = MoneyField(default=0)
    work_completed_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["invoice"], name="idx_invoiceline_invoice")]

    def save(self, *args, **kwargs):
        self.line_total = ((self.quantity or Decimal("0")) * (self.unit_cost or Decimal("0"))).quantize(
            Decimal("0.01")
        )
        super().save(*args, **kwargs)


class ChangeOrder(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("void", "Void"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="change_orders")
    commitment = models.ForeignKey(
        Commitment, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_orders"
    )
    number = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    reason = models.CharField(max_length=255, blank=True)
    amount = MoneyField(default=0)
    schedule_impact_days = models.IntegerField(default=0)
    cost_code = models.ForeignKey(
        CostCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_orders"
    )
    currency = models.CharField(max_length=3, default="USD")
    submitted_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_orders_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_orders_created"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_changeorder_project_number")
        ]
        indexes = [models.Index(fields=["project", "status"], name="idx_co_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return f"CO {self.number}: {self.title}"


class Retention(Base):
    """Retention withheld on a commitment/invoice."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="retentions")
    commitment = models.ForeignKey(
        Commitment, on_delete=models.CASCADE, null=True, blank=True, related_name="retentions"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name="retentions"
    )
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    withheld_amount = MoneyField(default=0)
    released_amount = MoneyField(default=0)
    release_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project"], name="idx_retention_project")]

    @property
    def outstanding(self):
        return (self.withheld_amount or Decimal("0")) - (self.released_amount or Decimal("0"))


class Forecast(Base):
    """Cost forecast / estimate at completion for a budget line."""

    METHOD_CHOICES = [("manual", "Manual"), ("percent_complete", "Percent Complete"), ("trend", "Trend")]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="forecasts")
    budget_line = models.ForeignKey(
        BudgetLine, on_delete=models.CASCADE, related_name="forecasts"
    )
    period = models.DateField(db_index=True)
    method = models.CharField(max_length=24, choices=METHOD_CHOICES, default="manual")
    estimate_to_complete = MoneyField(default=0)
    estimate_at_completion = MoneyField(default=0)
    projected_overrun = MoneyField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="forecasts_created"
    )

    class Meta:
        ordering = ["-period"]
        constraints = [
            models.UniqueConstraint(fields=["budget_line", "period"], name="uniq_forecast_line_period")
        ]
        indexes = [models.Index(fields=["project", "-period"], name="idx_forecast_project_period")]
