"""Financial workflow services.

Money-moving transitions run inside ``transaction.atomic`` with row locks so
concurrent approvals cannot double-post amounts.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event

from .models import Budget, BudgetLine, ChangeOrder, Commitment, Invoice, PurchaseOrder, Retention


def _assert_approval_scope(obj, user, request):
    membership = getattr(request, "membership", None)
    if membership is None or obj.project.organization_id != membership.organization_id:
        raise PermissionDenied("This record belongs to another organization.")
    if not user.can_access_project(obj.project):
        raise PermissionDenied("You do not have access to this project.")


def _positive_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter a valid amount."})
    if amount <= 0:
        raise ValidationError({"amount": "Must be greater than zero."})
    return amount.quantize(Decimal("0.01"))


def _assert_transition(current, allowed, label):
    if current not in allowed:
        raise ValidationError({"status": f"Cannot {label} from status '{current}'."})


@transaction.atomic
def approve_change_order(*, change_order_id, user, request=None):
    change_order = (
        ChangeOrder.objects.select_for_update()
        .select_related("project", "cost_code", "commitment")
        .get(pk=change_order_id)
    )
    _assert_approval_scope(change_order, user, request)
    if change_order.status == "approved":
        return change_order
    _assert_transition(change_order.status, {"draft", "pending"}, "approve")

    change_order.status = "approved"
    change_order.approved_by = user
    change_order.approved_at = timezone.now()
    change_order.approved_date = timezone.now().date()
    change_order.save(
        update_fields=["status", "approved_by", "approved_at", "approved_date", "updated_at"]
    )

    if change_order.amount:
        if change_order.commitment_id:
            commitment = Commitment.objects.select_for_update().get(pk=change_order.commitment_id)
            commitment.revised_amount = (commitment.revised_amount or 0) + change_order.amount
            commitment.save(update_fields=["revised_amount", "updated_at"])

        if change_order.cost_code_id:
            budget = (
                Budget.objects.filter(project=change_order.project)
                .order_by("-is_primary", "-created_at")
                .first()
            )
            if budget is not None:
                line, _ = BudgetLine.objects.select_for_update().get_or_create(
                    budget=budget,
                    cost_code=change_order.cost_code,
                    defaults={"project": change_order.project},
                )
                line.budgeted_amount = (line.budgeted_amount or 0) + change_order.amount
                line.save(update_fields=["budgeted_amount", "updated_at"])

    record_audit_event(
        organization=change_order.project.organization,
        actor=user,
        action="change_order.approved",
        target_type="ChangeOrder",
        target_id=change_order.id,
        project=change_order.project,
        metadata={"amount": str(change_order.amount)},
        request=request,
    )
    return change_order


@transaction.atomic
def submit_change_order(*, change_order_id, user, request=None):
    change_order = (
        ChangeOrder.objects.select_for_update().select_related("project").get(pk=change_order_id)
    )
    _assert_approval_scope(change_order, user, request)
    if change_order.status == "pending":
        return change_order
    _assert_transition(change_order.status, {"draft", "rejected", "void"}, "submit")
    change_order.status = "pending"
    change_order.submitted_date = change_order.submitted_date or timezone.now().date()
    change_order.save(update_fields=["status", "submitted_date", "updated_at"])
    record_audit_event(
        organization=change_order.project.organization,
        actor=user,
        action="change_order.submitted",
        target_type="ChangeOrder",
        target_id=change_order.id,
        project=change_order.project,
        request=request,
    )
    return change_order


@transaction.atomic
def reject_change_order(*, change_order_id, user, request=None):
    change_order = (
        ChangeOrder.objects.select_for_update().select_related("project").get(pk=change_order_id)
    )
    _assert_approval_scope(change_order, user, request)
    if change_order.status == "rejected":
        return change_order
    _assert_transition(change_order.status, {"pending"}, "reject")
    change_order.status = "rejected"
    change_order.save(update_fields=["status", "updated_at"])
    record_audit_event(
        organization=change_order.project.organization,
        actor=user,
        action="change_order.rejected",
        target_type="ChangeOrder",
        target_id=change_order.id,
        project=change_order.project,
        request=request,
    )
    return change_order


@transaction.atomic
def approve_commitment(*, commitment_id, user, request=None):
    commitment = Commitment.objects.select_for_update().select_related("project").get(pk=commitment_id)
    _assert_approval_scope(commitment, user, request)
    if commitment.status == "approved":
        return commitment
    _assert_transition(commitment.status, {"draft", "pending"}, "approve")
    commitment.status = "approved"
    commitment.approved_by = user
    commitment.approved_at = timezone.now()
    commitment.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_audit_event(
        organization=commitment.project.organization,
        actor=user,
        action="commitment.approved",
        target_type="Commitment",
        target_id=commitment.id,
        project=commitment.project,
        request=request,
    )
    return commitment


@transaction.atomic
def issue_commitment(*, commitment_id, user, request=None):
    commitment = Commitment.objects.select_for_update().select_related("project").get(pk=commitment_id)
    _assert_approval_scope(commitment, user, request)
    if commitment.status == "issued":
        return commitment
    _assert_transition(commitment.status, {"approved"}, "issue")
    commitment.status = "issued"
    commitment.issued_date = commitment.issued_date or timezone.now().date()
    commitment.save(update_fields=["status", "issued_date", "updated_at"])
    record_audit_event(
        organization=commitment.project.organization,
        actor=user,
        action="commitment.issued",
        target_type="Commitment",
        target_id=commitment.id,
        project=commitment.project,
        request=request,
    )
    return commitment


@transaction.atomic
def lock_budget(*, budget_id, user, request=None):
    budget = Budget.objects.select_for_update().select_related("project").get(pk=budget_id)
    _assert_approval_scope(budget, user, request)
    if budget.status == "locked":
        return budget
    _assert_transition(budget.status, {"draft"}, "lock")
    budget.status = "locked"
    budget.approved_by = user
    budget.approved_at = timezone.now()
    budget.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_audit_event(
        organization=budget.project.organization,
        actor=user,
        action="budget.locked",
        target_type="Budget",
        target_id=budget.id,
        project=budget.project,
        request=request,
    )
    return budget


@transaction.atomic
def approve_purchase_order(*, purchase_order_id, user, request=None):
    purchase_order = (
        PurchaseOrder.objects.select_for_update().select_related("project").get(pk=purchase_order_id)
    )
    _assert_approval_scope(purchase_order, user, request)
    if purchase_order.status == "approved":
        return purchase_order
    _assert_transition(purchase_order.status, {"draft", "pending"}, "approve")
    purchase_order.status = "approved"
    purchase_order.approved_by = user
    purchase_order.save(update_fields=["status", "approved_by", "updated_at"])
    record_audit_event(
        organization=purchase_order.project.organization,
        actor=user,
        action="purchase_order.approved",
        target_type="PurchaseOrder",
        target_id=purchase_order.id,
        project=purchase_order.project,
        request=request,
    )
    return purchase_order


@transaction.atomic
def receive_purchase_order(*, purchase_order_id, user, request=None):
    purchase_order = (
        PurchaseOrder.objects.select_for_update().select_related("project").get(pk=purchase_order_id)
    )
    _assert_approval_scope(purchase_order, user, request)
    if purchase_order.status == "received":
        return purchase_order
    _assert_transition(purchase_order.status, {"approved", "issued"}, "receive")
    purchase_order.status = "received"
    purchase_order.received_date = purchase_order.received_date or timezone.now().date()
    purchase_order.save(update_fields=["status", "received_date", "updated_at"])
    record_audit_event(
        organization=purchase_order.project.organization,
        actor=user,
        action="purchase_order.received",
        target_type="PurchaseOrder",
        target_id=purchase_order.id,
        project=purchase_order.project,
        request=request,
    )
    return purchase_order


@transaction.atomic
def approve_invoice(*, invoice_id, user, request=None):
    invoice = Invoice.objects.select_for_update().select_related("project", "commitment").get(pk=invoice_id)
    _assert_approval_scope(invoice, user, request)
    if invoice.status in {"approved", "paid", "partially_paid"}:
        return invoice
    _assert_transition(invoice.status, {"draft", "submitted", "under_review"}, "approve")
    invoice.status = "approved"
    invoice.approved_by = user
    invoice.approved_at = timezone.now()
    invoice.recalculate()
    invoice.save(update_fields=["status", "approved_by", "approved_at", "total_amount", "net_payable", "updated_at"])

    if invoice.commitment_id:
        commitment = Commitment.objects.select_for_update().get(pk=invoice.commitment_id)
        commitment.billed_amount = (commitment.billed_amount or 0) + invoice.total_amount
        commitment.save(update_fields=["billed_amount", "updated_at"])

    record_audit_event(
        organization=invoice.project.organization,
        actor=user,
        action="invoice.approved",
        target_type="Invoice",
        target_id=invoice.id,
        project=invoice.project,
        metadata={"total_amount": str(invoice.total_amount)},
        request=request,
    )
    return invoice


@transaction.atomic
def pay_invoice(*, invoice_id, amount, user, request=None):
    invoice = Invoice.objects.select_for_update().select_related("project").get(pk=invoice_id)
    _assert_approval_scope(invoice, user, request)
    _assert_transition(invoice.status, {"approved", "partially_paid"}, "pay")
    payment = _positive_amount(amount)
    outstanding = (invoice.net_payable or Decimal("0")) - (invoice.paid_amount or Decimal("0"))
    if payment > outstanding:
        raise ValidationError({"amount": "Payment exceeds the outstanding invoice balance."})
    invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + payment
    invoice.status = "paid" if invoice.paid_amount >= invoice.net_payable else "partially_paid"
    invoice.recalculate()
    invoice.save(update_fields=["paid_amount", "status", "total_amount", "net_payable", "updated_at"])
    record_audit_event(
        organization=invoice.project.organization,
        actor=user,
        action="invoice.paid",
        target_type="Invoice",
        target_id=invoice.id,
        project=invoice.project,
        metadata={"amount": str(payment)},
        request=request,
    )
    return invoice


@transaction.atomic
def release_retention(*, retention_id, amount, user, request=None):
    retention = Retention.objects.select_for_update().select_related("project").get(pk=retention_id)
    _assert_approval_scope(retention, user, request)
    release = _positive_amount(amount)
    if release > retention.outstanding:
        raise ValidationError({"amount": "Release exceeds the outstanding retention balance."})
    retention.released_amount = (retention.released_amount or Decimal("0")) + release
    retention.release_date = retention.release_date or timezone.now().date()
    retention.save(update_fields=["released_amount", "release_date", "updated_at"])
    record_audit_event(
        organization=retention.project.organization,
        actor=user,
        action="retention.released",
        target_type="Retention",
        target_id=retention.id,
        project=retention.project,
        metadata={"amount": str(release)},
        request=request,
    )
    return retention
