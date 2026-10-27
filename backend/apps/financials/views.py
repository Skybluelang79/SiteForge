"""Financial workflows with atomic approval services."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.viewsets import ProjectScopedViewSet

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
from .serializers import (
    BudgetLineSerializer,
    BudgetSerializer,
    ChangeOrderSerializer,
    CommitmentLineSerializer,
    CommitmentSerializer,
    CostCodeSerializer,
    ForecastSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    PurchaseOrderLineSerializer,
    PurchaseOrderSerializer,
    RetentionSerializer,
)
from .services import approve_change_order, approve_commitment, approve_invoice, approve_purchase_order


class CostCodeViewSet(ProjectScopedViewSet):
    serializer_class = CostCodeSerializer
    filterset_fields = ["project", "parent", "is_active"]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["code", "created_at"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }


class BudgetViewSet(ProjectScopedViewSet):
    serializer_class = BudgetSerializer
    filterset_fields = ["project", "status", "is_primary", "created_by"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "version"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "lock": ("financials.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("created_by", "approved_by").prefetch_related("lines")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="lock")
    def lock(self, request, pk=None):
        budget = self.get_object()
        budget.status = "locked"
        budget.approved_by = request.user
        budget.approved_at = __import__("django.utils.timezone", fromlist=["now"]).now()
        budget.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(BudgetSerializer(budget).data)


class BudgetLineViewSet(ProjectScopedViewSet):
    serializer_class = BudgetLineSerializer
    filterset_fields = ["budget", "project", "cost_code"]
    search_fields = ["description"]
    ordering = ["cost_code__code"]
    org_field = "budget__project__organization_id"
    project_field = "budget__project_id"
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }

    def perform_create(self, serializer):
        budget = serializer.validated_data.get("budget")
        from rest_framework.exceptions import PermissionDenied

        if budget is None or not self.request.user.can_access_project(budget.project):
            raise PermissionDenied("You do not have access to this budget's project.")
        serializer.save()


class CommitmentViewSet(ProjectScopedViewSet):
    serializer_class = CommitmentSerializer
    filterset_fields = ["project", "status", "commitment_type", "contract"]
    search_fields = ["number", "title", "vendor_name", "description"]
    ordering_fields = ["created_at", "issued_date", "status"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "approve": ("financials.approve",),
        "issue": ("financials.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("approved_by", "created_by", "contract").prefetch_related("lines")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        commitment = approve_commitment(commitment_id=pk, user=request.user, request=request)
        return Response(CommitmentSerializer(commitment).data)

    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        commitment = self.get_object()
        commitment.status = "issued"
        from django.utils import timezone

        commitment.issued_date = commitment.issued_date or timezone.now().date()
        commitment.save(update_fields=["status", "issued_date", "updated_at"])
        return Response(CommitmentSerializer(commitment).data)

    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, pk=None):
        commitment = self.get_object()
        if request.method == "GET":
            return Response(CommitmentLineSerializer(commitment.lines.all(), many=True).data)
        serializer = CommitmentLineSerializer(data={**request.data, "commitment": str(commitment.id)})
        serializer.is_valid(raise_exception=True)
        line = serializer.save()
        return Response(CommitmentLineSerializer(line).data, status=status.HTTP_201_CREATED)


class CommitmentLineViewSet(ProjectScopedViewSet):
    serializer_class = CommitmentLineSerializer
    filterset_fields = ["commitment"]
    org_field = "commitment__project__organization_id"
    project_field = "commitment__project_id"
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }

    def perform_create(self, serializer):
        commitment = serializer.validated_data.get("commitment")
        from rest_framework.exceptions import PermissionDenied

        if commitment is None or not self.request.user.can_access_project(commitment.project):
            raise PermissionDenied("You do not have access to this commitment's project.")
        serializer.save()


class PurchaseOrderViewSet(ProjectScopedViewSet):
    serializer_class = PurchaseOrderSerializer
    filterset_fields = ["project", "status", "commitment"]
    search_fields = ["number", "title", "vendor_name"]
    ordering_fields = ["created_at", "order_date"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "approve": ("financials.approve",),
        "receive": ("financials.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("approved_by", "created_by", "commitment").prefetch_related("lines")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        po = approve_purchase_order(purchase_order_id=pk, user=request.user, request=request)
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, pk=None):
        po = self.get_object()
        po.status = "received"
        from django.utils import timezone

        po.received_date = po.received_date or timezone.now().date()
        po.save(update_fields=["status", "received_date", "updated_at"])
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, pk=None):
        po = self.get_object()
        if request.method == "GET":
            return Response(PurchaseOrderLineSerializer(po.lines.all(), many=True).data)
        serializer = PurchaseOrderLineSerializer(data={**request.data, "purchase_order": str(po.id)})
        serializer.is_valid(raise_exception=True)
        line = serializer.save()
        return Response(PurchaseOrderLineSerializer(line).data, status=status.HTTP_201_CREATED)


class PurchaseOrderLineViewSet(ProjectScopedViewSet):
    serializer_class = PurchaseOrderLineSerializer
    filterset_fields = ["purchase_order"]
    org_field = "purchase_order__project__organization_id"
    project_field = "purchase_order__project_id"
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }

    def perform_create(self, serializer):
        po = serializer.validated_data.get("purchase_order")
        from rest_framework.exceptions import PermissionDenied

        if po is None or not self.request.user.can_access_project(po.project):
            raise PermissionDenied("You do not have access to this purchase order's project.")
        serializer.save()


class InvoiceViewSet(ProjectScopedViewSet):
    serializer_class = InvoiceSerializer
    filterset_fields = ["project", "status", "commitment", "purchase_order", "due_date"]
    search_fields = ["number", "vendor_invoice_number", "vendor_name"]
    ordering_fields = ["created_at", "invoice_date", "due_date"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "approve": ("financials.approve",),
        "pay": ("financials.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "approved_by", "created_by", "commitment", "purchase_order"
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        invoice = serializer.save(created_by=self.request.user)
        invoice.recalculate()
        invoice.save(update_fields=["total_amount", "net_payable", "updated_at"])

    def perform_update(self, serializer):
        invoice = serializer.save()
        invoice.recalculate()
        invoice.save(update_fields=["total_amount", "net_payable", "updated_at"])

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        invoice = approve_invoice(invoice_id=pk, user=request.user, request=request)
        invoice.recalculate()
        invoice.save(update_fields=["total_amount", "net_payable", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        invoice = self.get_object()
        amount = request.data.get("paid_amount")
        if amount is not None:
            from decimal import Decimal

            invoice.paid_amount = Decimal(str(amount))
        if invoice.paid_amount >= invoice.net_payable:
            invoice.status = "paid"
        else:
            invoice.status = "partially_paid"
        invoice.save(update_fields=["paid_amount", "status", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, pk=None):
        invoice = self.get_object()
        if request.method == "GET":
            return Response(InvoiceLineSerializer(invoice.lines.all(), many=True).data)
        serializer = InvoiceLineSerializer(data={**request.data, "invoice": str(invoice.id)})
        serializer.is_valid(raise_exception=True)
        line = serializer.save()
        invoice.recalculate()
        invoice.save(update_fields=["total_amount", "net_payable", "updated_at"])
        return Response(InvoiceLineSerializer(line).data, status=status.HTTP_201_CREATED)


class InvoiceLineViewSet(ProjectScopedViewSet):
    serializer_class = InvoiceLineSerializer
    filterset_fields = ["invoice"]
    org_field = "invoice__project__organization_id"
    project_field = "invoice__project_id"
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }

    def perform_create(self, serializer):
        invoice = serializer.validated_data.get("invoice")
        from rest_framework.exceptions import PermissionDenied

        if invoice is None or not self.request.user.can_access_project(invoice.project):
            raise PermissionDenied("You do not have access to this invoice's project.")
        line = serializer.save()
        invoice.recalculate()
        invoice.save(update_fields=["total_amount", "net_payable", "updated_at"])
        return line


class ChangeOrderViewSet(ProjectScopedViewSet):
    serializer_class = ChangeOrderSerializer
    filterset_fields = ["project", "status", "commitment"]
    search_fields = ["number", "title", "description"]
    ordering_fields = ["created_at", "submitted_date"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "submit": ("financials.edit",),
        "approve": ("financials.approve",),
        "reject": ("financials.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("approved_by", "created_by", "commitment", "cost_code")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        co = self.get_object()
        co.status = "pending"
        from django.utils import timezone

        co.submitted_date = co.submitted_date or timezone.now().date()
        co.save(update_fields=["status", "submitted_date", "updated_at"])
        return Response(ChangeOrderSerializer(co).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        co = approve_change_order(change_order_id=pk, user=request.user, request=request)
        return Response(ChangeOrderSerializer(co).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        co = self.get_object()
        co.status = "rejected"
        co.save(update_fields=["status", "updated_at"])
        return Response(ChangeOrderSerializer(co).data)


class RetentionViewSet(ProjectScopedViewSet):
    serializer_class = RetentionSerializer
    filterset_fields = ["project", "commitment", "invoice"]
    ordering = ["-created_at"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
        "release": ("financials.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("commitment", "invoice")

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        retention = self.get_object()
        amount = request.data.get("amount")
        from decimal import Decimal

        if amount is not None:
            retention.released_amount = (retention.released_amount or Decimal("0")) + Decimal(str(amount))
        else:
            retention.released_amount = retention.withheld_amount
        from django.utils import timezone

        retention.release_date = retention.release_date or timezone.now().date()
        retention.save(update_fields=["released_amount", "release_date", "updated_at"])
        return Response(RetentionSerializer(retention).data)


class ForecastViewSet(ProjectScopedViewSet):
    serializer_class = ForecastSerializer
    filterset_fields = ["project", "budget_line", "method", "period"]
    ordering = ["-period"]
    action_permissions = {
        "read": ("financials.view",),
        "create": ("financials.create",),
        "update": ("financials.edit",),
        "partial_update": ("financials.edit",),
        "destroy": ("financials.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("budget_line", "created_by")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
