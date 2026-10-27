from rest_framework.routers import DefaultRouter

from .views import (
    BudgetLineViewSet,
    BudgetViewSet,
    ChangeOrderViewSet,
    CommitmentLineViewSet,
    CommitmentViewSet,
    CostCodeViewSet,
    ForecastViewSet,
    InvoiceLineViewSet,
    InvoiceViewSet,
    PurchaseOrderLineViewSet,
    PurchaseOrderViewSet,
    RetentionViewSet,
)

router = DefaultRouter()
router.register("cost-codes", CostCodeViewSet, basename="cost-code")
router.register("budgets", BudgetViewSet, basename="budget")
router.register("budget-lines", BudgetLineViewSet, basename="budget-line")
router.register("commitments", CommitmentViewSet, basename="commitment")
router.register("commitment-lines", CommitmentLineViewSet, basename="commitment-line")
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-order")
router.register("purchase-order-lines", PurchaseOrderLineViewSet, basename="purchase-order-line")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("invoice-lines", InvoiceLineViewSet, basename="invoice-line")
router.register("change-orders", ChangeOrderViewSet, basename="change-order")
router.register("retentions", RetentionViewSet, basename="retention")
router.register("forecasts", ForecastViewSet, basename="forecast")

urlpatterns = router.urls
