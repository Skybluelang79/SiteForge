"""Financial workflow services.

Money-moving transitions run inside ``transaction.atomic`` with row locks so
concurrent approvals cannot double-post amounts.
"""
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit_event

from .models import Budget, BudgetLine, ChangeOrder, Commitment, Invoice, PurchaseOrder


@transaction.atomic
def approve_change_order(*, change_order_id, user, request=None):
    change_order = (
        ChangeOrder.objects.select_for_update()
        .select_related("project", "cost_code", "commitment")
        .get(pk=change_order_id)
    )
    if change_order.status == "approved":
        return change_order

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
def approve_commitment(*, commitment_id, user, request=None):
    commitment = Commitment.objects.select_for_update().select_related("project").get(pk=commitment_id)
    if commitment.status == "approved":
        return commitment
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
def approve_purchase_order(*, purchase_order_id, user, request=None):
    purchase_order = (
        PurchaseOrder.objects.select_for_update().select_related("project").get(pk=purchase_order_id)
    )
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
def approve_invoice(*, invoice_id, user, request=None):
    invoice = Invoice.objects.select_for_update().select_related("project", "commitment").get(pk=invoice_id)
    if invoice.status == "approved":
        return invoice
    invoice.status = "approved"
    invoice.approved_by = user
    invoice.approved_at = timezone.now()
    invoice.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

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
