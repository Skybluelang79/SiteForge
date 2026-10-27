from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalChainStepViewSet,
    ApprovalChainViewSet,
    CommentViewSet,
    RFICommentViewSet,
    RFIViewSet,
    SubmittalApprovalViewSet,
    SubmittalItemViewSet,
    SubmittalViewSet,
)

router = DefaultRouter()
router.register("rfis", RFIViewSet, basename="rfi")
router.register("rfi-comments", RFICommentViewSet, basename="rfi-comment")
router.register("submittals", SubmittalViewSet, basename="submittal")
router.register("submittal-items", SubmittalItemViewSet, basename="submittal-item")
router.register("approval-chains", ApprovalChainViewSet, basename="approval-chain")
router.register("approval-chain-steps", ApprovalChainStepViewSet, basename="approval-chain-step")
router.register("submittal-approvals", SubmittalApprovalViewSet, basename="submittal-approval")
router.register("comments", CommentViewSet, basename="comment")

urlpatterns = router.urls
