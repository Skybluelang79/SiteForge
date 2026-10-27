"""Financial serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    Budget,
    BudgetLine,
    ChangeOrder,
    Commitment,
    CommitmentLine,
    CostCode,
    Forecast,
    Invoice,
    InvoiceLine,
    PurchaseOrder,
    PurchaseOrderLine,
    Retention,
)


class CostCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostCode
        fields = [
            "id", "project", "code", "name", "parent", "description", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        parent = attrs.get("parent") or getattr(self.instance, "parent", None)
        if project and parent and parent.project_id != project.id:
            raise serializers.ValidationError({"parent": "Parent cost code belongs to another project."})
        code = attrs.get("code") or getattr(self.instance, "code", None)
        if project and code:
            qs = CostCode.objects.filter(project=project, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"code": "This cost code already exists."})
        return attrs


class BudgetLineSerializer(serializers.ModelSerializer):
    variance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            "id", "budget", "project", "cost_code", "description", "budgeted_amount",
            "committed_amount", "actual_amount", "forecast_amount", "quantity", "unit_cost",
            "variance", "remaining", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "variance", "remaining", "created_at", "updated_at"]

    def validate(self, attrs):
        budget = attrs.get("budget") or getattr(self.instance, "budget", None)
        project = attrs.get("project") or getattr(self.instance, "project", None)
        cost_code = attrs.get("cost_code") or getattr(self.instance, "cost_code", None)
        if budget and project and budget.project_id != project.id:
            raise serializers.ValidationError({"project": "Budget belongs to another project."})
        if project and cost_code and cost_code.project_id != project.id:
            raise serializers.ValidationError({"cost_code": "Cost code belongs to another project."})
        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    lines = BudgetLineSerializer(many=True, read_only=True)
    total_budgeted = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            "id", "project", "name", "version", "status", "currency", "is_primary",
            "approved_by", "approved_at", "created_by", "lines", "total_budgeted",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "approved_by", "approved_at", "created_by", "created_at", "updated_at"]

    def get_total_budgeted(self, obj):
        return sum((line.budgeted_amount for line in obj.lines.all()), 0)


class CommitmentLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommitmentLine
        fields = [
            "id", "commitment", "cost_code", "description", "amount", "quantity",
            "unit_cost", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        commitment = attrs.get("commitment") or getattr(self.instance, "commitment", None)
        cost_code = attrs.get("cost_code") or getattr(self.instance, "cost_code", None)
        if commitment and cost_code and cost_code.project_id != commitment.project_id:
            raise serializers.ValidationError({"cost_code": "Cost code belongs to another project."})
        return attrs


class CommitmentSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    retention_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    open_balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    lines = CommitmentLineSerializer(many=True, read_only=True)

    class Meta:
        model = Commitment
        fields = [
            "id", "project", "contract", "number", "title", "commitment_type", "status",
            "vendor_name", "vendor_email", "description", "original_amount", "revised_amount",
            "billed_amount", "retention_percent", "currency", "issued_date", "start_date",
            "end_date", "approved_by", "approved_at", "created_by", "retention_amount",
            "open_balance", "lines", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "approved_by", "approved_at", "created_by", "retention_amount",
            "open_balance", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = Commitment.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "This commitment number exists."})
        return attrs


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id", "purchase_order", "cost_code", "description", "quantity", "unit_cost",
            "line_total", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "line_total", "created_at", "updated_at"]

    def validate(self, attrs):
        po = attrs.get("purchase_order") or getattr(self.instance, "purchase_order", None)
        cost_code = attrs.get("cost_code") or getattr(self.instance, "cost_code", None)
        if po and cost_code and cost_code.project_id != po.project_id:
            raise serializers.ValidationError({"cost_code": "Cost code belongs to another project."})
        return attrs


class PurchaseOrderSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "project", "commitment", "number", "title", "status", "vendor_name",
            "vendor_reference", "description", "subtotal", "tax_amount", "shipping_amount",
            "total_amount", "currency", "order_date", "expected_delivery_date", "received_date",
            "approved_by", "created_by", "lines", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "total_amount", "approved_by", "created_by", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = PurchaseOrder.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "This purchase order number exists."})
        return attrs


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "id", "invoice", "cost_code", "description", "quantity", "unit_cost",
            "line_total", "scheduled_value", "work_completed_percent", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "line_total", "created_at", "updated_at"]

    def validate(self, attrs):
        invoice = attrs.get("invoice") or getattr(self.instance, "invoice", None)
        cost_code = attrs.get("cost_code") or getattr(self.instance, "cost_code", None)
        if invoice and cost_code and cost_code.project_id != invoice.project_id:
            raise serializers.ValidationError({"cost_code": "Cost code belongs to another project."})
        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "project", "commitment", "purchase_order", "number", "vendor_invoice_number",
            "title", "status", "vendor_name", "period_start", "period_end", "invoice_date",
            "due_date", "subtotal", "tax_amount", "total_amount", "retention_amount",
            "net_payable", "paid_amount", "currency", "approved_by", "approved_at",
            "created_by", "lines", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "total_amount", "net_payable", "approved_by", "approved_at",
            "created_by", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = Invoice.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "This invoice number exists."})
        return attrs


class ChangeOrderSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ChangeOrder
        fields = [
            "id", "project", "commitment", "number", "title", "description", "status",
            "reason", "amount", "schedule_impact_days", "cost_code", "currency",
            "submitted_date", "approved_date", "approved_by", "approved_at", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "approved_by", "approved_at", "created_by", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = ChangeOrder.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "This change order number exists."})
        return attrs


class RetentionSerializer(serializers.ModelSerializer):
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Retention
        fields = [
            "id", "project", "commitment", "invoice", "percent", "withheld_amount",
            "released_amount", "release_date", "notes", "outstanding", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "outstanding", "created_at", "updated_at"]


class ForecastSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Forecast
        fields = [
            "id", "project", "budget_line", "period", "method", "estimate_to_complete",
            "estimate_at_completion", "projected_overrun", "notes", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        budget_line = attrs.get("budget_line") or getattr(self.instance, "budget_line", None)
        if project and budget_line and budget_line.project_id != project.id:
            raise serializers.ValidationError({"budget_line": "Budget line belongs to another project."})
        return attrs
