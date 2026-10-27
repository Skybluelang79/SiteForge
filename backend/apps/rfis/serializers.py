"""RFI, submittal, approval and comment serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    ApprovalChain,
    ApprovalChainStep,
    Comment,
    RFI,
    RFIComment,
    Submittal,
    SubmittalApproval,
    SubmittalItem,
)


class RFICommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = RFIComment
        fields = ["id", "rfi", "author", "body", "is_official", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class RFISerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    assigned_to = UserSummarySerializer(read_only=True)
    ball_in_court = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    ball_in_court_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    comments = RFICommentSerializer(many=True, read_only=True)

    class Meta:
        model = RFI
        fields = [
            "id", "project", "number", "subject", "question", "official_response", "status",
            "priority", "cost_impact", "schedule_impact", "cost_impact_amount",
            "schedule_impact_days", "drawing", "assigned_to", "assigned_to_id",
            "ball_in_court", "ball_in_court_id", "created_by", "due_date", "answered_at",
            "closed_at", "comments", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "official_response", "status", "answered_at", "closed_at",
            "created_by", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = RFI.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "An RFI with this number already exists."})
        return attrs


class RFIResponseSerializer(serializers.Serializer):
    official_response = serializers.CharField()
    status = serializers.ChoiceField(
        choices=[("answered", "Answered"), ("closed", "Closed")], default="answered"
    )


class SubmittalItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmittalItem
        fields = [
            "id", "submittal", "description", "spec_reference", "file", "status",
            "review_notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubmittalSerializer(serializers.ModelSerializer):
    submitted_by = UserSummarySerializer(read_only=True)
    reviewer = UserSummarySerializer(read_only=True)
    reviewer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    items = SubmittalItemSerializer(many=True, read_only=True)
    approvals = serializers.SerializerMethodField()

    class Meta:
        model = Submittal
        fields = [
            "id", "project", "number", "title", "submittal_type", "spec_section", "revision",
            "status", "description", "submitted_by", "reviewer", "reviewer_id", "due_date",
            "required_by", "submitted_at", "reviewed_at", "items", "approvals",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "submitted_by", "reviewed_at", "submitted_at", "created_at", "updated_at",
        ]

    def get_approvals(self, obj):
        return [
            {
                "id": str(a.id),
                "decision": a.decision,
                "comments": a.comments,
                "decided_at": a.decided_at,
                "approver": a.approver_id,
            }
            for a in obj.approvals.all()
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        revision = attrs.get("revision") or getattr(self.instance, "revision", "0")
        if project and number:
            qs = Submittal.objects.filter(project=project, number=number, revision=revision)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"number": "A submittal with this number and revision already exists."}
                )
        return attrs


class SubmittalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=SubmittalApproval.DECISION_CHOICES)
    comments = serializers.CharField(required=False, allow_blank=True, default="")


class ApprovalChainStepSerializer(serializers.ModelSerializer):
    approver = UserSummarySerializer(read_only=True)
    approver_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = ApprovalChainStep
        fields = [
            "id", "chain", "order", "approver", "approver_id", "role_code", "is_required",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "approver", "created_at", "updated_at"]


class ApprovalChainSerializer(serializers.ModelSerializer):
    steps = ApprovalChainStepSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalChain
        fields = [
            "id", "project", "name", "target_type", "is_active", "steps",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubmittalApprovalSerializer(serializers.ModelSerializer):
    approver = UserSummarySerializer(read_only=True)

    class Meta:
        model = SubmittalApproval
        fields = [
            "id", "submittal", "step", "approver", "decision", "comments",
            "decided_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "approver", "decided_at", "created_at", "updated_at"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id", "project", "target_type", "target_id", "parent", "author", "body",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]
