"""Create synthetic demo data across every SiteForge module."""
import base64
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import Document, DocumentFolder
from apps.documents.services import add_version
from apps.drawings.models import Drawing, DrawingSet
from apps.drawings.services import add_revision
from apps.field.models import DailyLog, EquipmentEntry, FieldPhoto, LabourEntry, Observation, WeatherRecord
from apps.financials.models import (
    Budget,
    BudgetLine,
    ChangeOrder,
    Commitment,
    CommitmentLine,
    CostCode,
    Forecast,
    Invoice,
    PurchaseOrder,
    Retention,
)
from apps.financials.services import approve_change_order, approve_invoice
from apps.integrations.models import ApiApplication, WebhookSubscription
from apps.integrations.services import generate_webhook_secret, issue_credentials
from apps.notifications.services import notify
from apps.organizations.models import Membership, Organization, Role
from apps.organizations.services import create_organization
from apps.projects.models import Milestone, Project, ProjectMember
from apps.quality.models import (
    CorrectiveAction,
    Defect,
    Inspection,
    InspectionItem,
    PunchList,
    PunchListItem,
    SafetyIncident,
)
from apps.reports.models import Dashboard, ReportDefinition
from apps.reports.services import collect_metrics_for_org
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task

DEMO_SLUG = "acme-demo"
DEMO_PASSWORD = "DemoPass123!"
DEMO_USERS = [
    ("owner@demo.siteforge.test", "Olivia", "Owner", "owner"),
    ("pm@demo.siteforge.test", "Paul", "Manager", "admin"),
    ("super@demo.siteforge.test", "Sam", "Supervisor", "member"),
    ("viewer@demo.siteforge.test", "Vera", "Viewer", "viewer"),
]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z0WQAAAAASUVORK5CYII="
)


class Command(BaseCommand):
    help = "Seed a demo organization, users, projects and sample records in every module."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and recreate the demo data.")

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Organization.objects.filter(slug=DEMO_SLUG).first()
        if existing is not None:
            if not options["reset"]:
                self.stdout.write(self.style.WARNING("Demo data already exists. Use --reset to recreate."))
                self._print_credentials()
                return
            Organization.objects.filter(pk=existing.pk).hard_delete()
            User.objects.filter(email__in=[entry[0] for entry in DEMO_USERS]).delete()

        today = timezone.now().date()
        users = {}
        for email, first_name, last_name, role_code in DEMO_USERS:
            user = User.objects.create_user(
                email=email,
                password=DEMO_PASSWORD,
                first_name=first_name,
                last_name=last_name,
            )
            users[role_code] = user
        owner = users["owner"]

        organization = create_organization(
            name="Acme Construction",
            owner=owner,
            slug=DEMO_SLUG,
            timezone="America/New_York",
            city="Boston",
            region="MA",
            country="USA",
        )
        for role_code, user in users.items():
            if role_code == "owner":
                continue
            Membership.objects.create(
                organization=organization,
                user=user,
                role_code=role_code,
                role=Role.objects.get(organization=organization, code=role_code),
                is_active=True,
                joined_at=timezone.now(),
            )

        project = Project.objects.create(
            organization=organization,
            name="Harbor Point Tower",
            number="HPT-2026",
            description="18-story mixed-use tower with below-grade parking.",
            status="active",
            project_type="Commercial",
            address_line1="100 Harbor Point Drive",
            city="Boston",
            region="MA",
            postal_code="02210",
            country="USA",
            start_date=today - timedelta(days=180),
            target_completion_date=today + timedelta(days=240),
            contract_value=Decimal("48500000.00"),
            client_name="Harbor Point Partners",
            project_manager=users["admin"],
            is_public=True,
        )
        for role_code, user in users.items():
            ProjectMember.objects.create(
                project=project,
                user=user,
                role_code=role_code if role_code in {"owner", "admin", "member", "viewer"} else "member",
                title=role_code.title(),
                is_active=True,
            )

        Milestone.objects.create(
            project=project,
            name="Foundation complete",
            due_date=today - timedelta(days=45),
            status="achieved",
            achieved_date=today - timedelta(days=47),
            weight=3,
            owner=users["admin"],
        )
        Milestone.objects.create(
            project=project,
            name="Structure topped out",
            due_date=today + timedelta(days=90),
            status="in_progress",
            weight=5,
            owner=users["admin"],
        )

        cost_codes = {}
        for code, name in [
            ("01-000", "General Conditions"),
            ("03-000", "Concrete"),
            ("05-000", "Structural Steel"),
            ("09-000", "Finishes"),
        ]:
            cost_codes[code] = CostCode.objects.create(project=project, code=code, name=name)

        budget = Budget.objects.create(
            project=project,
            name="Baseline Budget",
            version=1,
            status="active",
            is_primary=True,
            approved_by=owner,
            approved_at=timezone.now(),
            created_by=owner,
        )
        budget_lines = {}
        for code, amount in [
            ("01-000", "1800000.00"),
            ("03-000", "9600000.00"),
            ("05-000", "7200000.00"),
            ("09-000", "5400000.00"),
        ]:
            budget_lines[code] = BudgetLine.objects.create(
                budget=budget,
                project=project,
                cost_code=cost_codes[code],
                description=f"Budget for {cost_codes[code].name}",
                budgeted_amount=Decimal(amount),
                committed_amount=Decimal(amount) * Decimal("0.35"),
                actual_amount=Decimal(amount) * Decimal("0.18"),
                forecast_amount=Decimal(amount) * Decimal("1.02"),
            )

        commitment = Commitment.objects.create(
            project=project,
            number="SC-001",
            title="Concrete package",
            commitment_type="subcontract",
            status="approved",
            vendor_name="Beacon Concrete LLC",
            vendor_email="billing@beaconconcrete.test",
            original_amount=Decimal("9200000.00"),
            revised_amount=Decimal("9200000.00"),
            approved_by=owner,
            approved_at=timezone.now(),
            issued_date=today - timedelta(days=120),
            created_by=owner,
        )
        CommitmentLine.objects.create(
            commitment=commitment,
            cost_code=cost_codes["03-000"],
            description="Concrete supply and placement",
            amount=Decimal("9200000.00"),
            quantity=Decimal("24000.0000"),
            unit_cost=Decimal("383.3333"),
        )

        purchase_order = PurchaseOrder.objects.create(
            project=project,
            commitment=None,
            number="PO-001",
            title="Rebar package",
            status="approved",
            vendor_name="Steel Supply Co.",
            subtotal=Decimal("120000.00"),
            tax_amount=Decimal("7500.00"),
            shipping_amount=Decimal("2500.00"),
            approved_by=owner,
            order_date=today - timedelta(days=30),
            created_by=owner,
        )

        invoice = Invoice.objects.create(
            project=project,
            commitment=commitment,
            number="INV-001",
            vendor_invoice_number="BC-4412",
            title="Concrete progress billing #1",
            status="submitted",
            vendor_name="Beacon Concrete LLC",
            period_start=today - timedelta(days=30),
            period_end=today,
            invoice_date=today,
            due_date=today + timedelta(days=30),
            subtotal=Decimal("450000.00"),
            tax_amount=Decimal("0.00"),
            retention_amount=Decimal("22500.00"),
            created_by=owner,
        )
        invoice.recalculate()
        invoice.save()
        approve_invoice(invoice_id=invoice.id, user=owner)

        change_order = ChangeOrder.objects.create(
            project=project,
            commitment=commitment,
            number="CO-001",
            title="Additional mat foundation",
            description="Owner-directed additional mat foundation volume.",
            status="pending",
            reason="Owner request",
            amount=Decimal("85000.00"),
            schedule_impact_days=4,
            cost_code=cost_codes["03-000"],
            submitted_date=today - timedelta(days=10),
            created_by=users["admin"],
        )
        approve_change_order(change_order_id=change_order.id, user=owner)

        Retention.objects.create(
            project=project,
            commitment=commitment,
            invoice=invoice,
            percent=Decimal("5.00"),
            withheld_amount=Decimal("22500.00"),
            notes="Standard 5% retention on concrete package.",
        )

        Forecast.objects.create(
            project=project,
            budget_line=budget_lines["03-000"],
            period=today.replace(day=1),
            method="manual",
            estimate_to_complete=Decimal("8000000.00"),
            estimate_at_completion=Decimal("9800000.00"),
            projected_overrun=Decimal("200000.00"),
            notes="Concrete escalation forecast.",
            created_by=users["admin"],
        )

        folder = DocumentFolder.objects.create(
            project=project,
            name="Project Directory",
            path="Project Directory",
            created_by=owner,
        )
        document = Document.objects.create(
            project=project,
            folder=folder,
            title="Project Directory and Site Contacts",
            description="Rolling project directory.",
            document_type="Directory",
            status="approved",
            created_by=owner,
            reviewed_by=users["admin"],
        )
        add_version(
            document=document,
            uploaded_file=ContentFile(b"SiteForge demo project directory\n", name="project-directory.txt"),
            uploaded_by=owner,
            change_note="Initial issue",
            content_type="text/plain",
        )
        Document.objects.create(
            project=project,
            folder=folder,
            title="Safety Plan",
            description="Site-specific safety plan.",
            document_type="Safety",
            status="in_review",
            created_by=users["member"],
        )

        structural = DrawingSet.objects.create(
            project=project, name="Structural", discipline="Structural"
        )
        drawing = Drawing.objects.create(
            project=project,
            drawing_set=structural,
            title="Foundation Plan",
            number="S-101",
            discipline="Structural",
            status="draft",
            created_by=owner,
        )
        add_revision(
            drawing=drawing,
            uploaded_file=ContentFile(b"SiteForge demo drawing placeholder\n", name="S-101-A.txt"),
            revision_code="A",
            revision_date=today - timedelta(days=20),
            change_summary="Issued for construction",
            uploaded_by=owner,
        )
        Drawing.objects.create(
            project=project,
            drawing_set=structural,
            title="Typical Column Details",
            number="S-301",
            discipline="Structural",
            status="draft",
            created_by=owner,
        )

        daily_log = DailyLog.objects.create(
            project=project,
            log_date=today,
            status="submitted",
            weather_summary="Clear, light wind",
            temperature_low_c=Decimal("12.0"),
            temperature_high_c=Decimal("21.0"),
            precipitation_mm=Decimal("0.00"),
            wind_speed_kph=Decimal("9.00"),
            work_activities="Level 8 slab prep and column formwork.",
            delays="None",
            safety_notes="Toolbox talk on fall protection completed.",
            visitors="Owner representative walkthrough at 10:00.",
            created_by=users["member"],
        )
        LabourEntry.objects.create(
            daily_log=daily_log,
            trade="Concrete",
            company="Beacon Concrete LLC",
            worker_count=14,
            hours_worked=Decimal("112.00"),
            overtime_hours=Decimal("8.00"),
        )
        EquipmentEntry.objects.create(
            daily_log=daily_log,
            equipment_name="Tower crane",
            equipment_code="TC-01",
            owner="Acme Construction",
            hours_used=Decimal("9.00"),
            idle_hours=Decimal("1.00"),
        )
        WeatherRecord.objects.create(
            project=project,
            record_date=today,
            source="manual",
            condition="Clear",
            temperature_c=Decimal("18.5"),
            humidity_percent=Decimal("54.00"),
            precipitation_mm=Decimal("0.00"),
            wind_speed_kph=Decimal("9.00"),
        )
        FieldPhoto.objects.create(
            project=project,
            daily_log=daily_log,
            caption="Level 8 slab prep",
            file=ContentFile(PNG_1X1, name="level-8-slab.png"),
            uploaded_by=users["member"],
        )
        Observation.objects.create(
            project=project,
            daily_log=daily_log,
            title="Housekeeping in laydown area",
            description="Packaging waste accumulating near the laydown area.",
            observation_type="concern",
            status="open",
            location="Level 2 laydown",
            assigned_to=users["member"],
            due_date=today + timedelta(days=3),
            created_by=users["member"],
        )

        tasks = [
            ("Complete level 8 slab pour", "in_progress", "high", today + timedelta(days=5), 45),
            ("Approve curtain wall shop drawings", "in_review", "critical", today + timedelta(days=2), 80),
            ("Close out foundation punch items", "todo", "medium", today + timedelta(days=14), 0),
            ("Update project schedule", "done", "medium", today - timedelta(days=3), 100),
        ]
        for title, status, priority, due_date, progress in tasks:
            Task.objects.create(
                project=project,
                title=title,
                status=status,
                priority=priority,
                assignee=users["admin"],
                start_date=today - timedelta(days=7),
                due_date=due_date,
                progress_percent=progress,
                created_by=owner,
            )

        answered_rfi = RFI.objects.create(
            project=project,
            number="RFI-001",
            subject="Beam depth at grid B",
            question="Confirm structural beam depth at grid B between levels 3 and 5.",
            official_response="Use 600 mm deep beam as detailed in S-301.",
            status="answered",
            priority="high",
            assigned_to=users["admin"],
            ball_in_court=users["member"],
            due_date=today + timedelta(days=5),
            answered_at=timezone.now(),
            created_by=users["member"],
        )
        RFI.objects.create(
            project=project,
            number="RFI-002",
            subject="Curtain wall anchor spacing",
            question="Confirm anchor spacing at typical curtain wall mullions.",
            status="open",
            priority="medium",
            assigned_to=users["admin"],
            due_date=today + timedelta(days=8),
            created_by=users["member"],
        )
        RFI.objects.create(
            project=project,
            number="RFI-003",
            subject="Elevator pit waterproofing",
            question="Confirm waterproofing membrane product for elevator pit.",
            status="overdue",
            priority="critical",
            assigned_to=users["admin"],
            due_date=today - timedelta(days=2),
            created_by=users["member"],
        )

        Submittal.objects.create(
            project=project,
            number="SUB-001",
            title="Curtain wall shop drawings",
            submittal_type="shop_drawing",
            spec_section="08 44 13",
            status="under_review",
            description="Curtain wall shop drawings and structural calculations.",
            submitted_by=users["admin"],
            reviewer=owner,
            due_date=today + timedelta(days=7),
            submitted_at=timezone.now(),
        )

        inspection = Inspection.objects.create(
            project=project,
            number="INS-001",
            title="Level 7 slab pre-pour",
            inspection_type="quality",
            status="passed",
            description="Pre-pour reinforcement and embed inspection.",
            location="Level 7, grid A-D",
            scheduled_date=today - timedelta(days=2),
            completed_date=today - timedelta(days=2),
            inspector=users["admin"],
            signed_off_by=owner,
            signed_off_at=timezone.now(),
            created_by=users["member"],
        )
        InspectionItem.objects.create(
            inspection=inspection,
            order=1,
            description="Rebar spacing and cover",
            result="pass",
        )
        InspectionItem.objects.create(
            inspection=inspection,
            order=2,
            description="Embed plates located per plan",
            result="pass",
        )
        Defect.objects.create(
            project=project,
            inspection=inspection,
            title="Honeycombing at column C-4",
            description="Minor honeycombing observed after form removal.",
            severity="medium",
            status="open",
            location="Level 7, column C-4",
            cost_code=cost_codes["03-000"],
            assigned_to=users["member"],
            due_date=today + timedelta(days=7),
            created_by=users["admin"],
        )
        punch_list = PunchList.objects.create(
            project=project,
            name="Level 7 punch list",
            description="Closeout items for level 7.",
            status="in_progress",
            target_date=today + timedelta(days=20),
            assigned_to=users["member"],
            created_by=users["admin"],
        )
        PunchListItem.objects.create(
            punch_list=punch_list,
            description="Touch up paint at corridor wall",
            location="Level 7 corridor",
            trade="Painting",
            status="open",
            assigned_to=users["member"],
            due_date=today + timedelta(days=10),
        )
        PunchListItem.objects.create(
            punch_list=punch_list,
            description="Replace damaged ceiling tile",
            location="Level 7 lobby",
            trade="Ceilings",
            status="closed",
            assigned_to=users["member"],
            closed_at=timezone.now(),
        )
        incident = SafetyIncident.objects.create(
            project=project,
            number="SI-001",
            title="Near miss - falling wrench",
            description="A wrench fell from level 5 and landed in a barricaded area.",
            severity="near_miss",
            status="investigating",
            occurred_at=timezone.now() - timedelta(days=4),
            location="Level 5, east elevation",
            witnesses="Two ironworkers",
            root_cause="Tool tethering not in use.",
            immediate_actions="Area barricaded and toolbox talk delivered.",
            osha_recordable=False,
            reported_by=users["member"],
            created_by=users["member"],
        )
        CorrectiveAction.objects.create(
            project=project,
            incident=incident,
            title="Require tool tethering above level 3",
            description="Update site policy and verify compliance daily.",
            status="in_progress",
            assigned_to=users["member"],
            due_date=today + timedelta(days=14),
            created_by=owner,
        )

        ReportDefinition.objects.create(
            organization=organization,
            project=project,
            name="Weekly RFI aging",
            report_type="rfi_aging",
            description="Open and overdue RFIs for the weekly owner meeting.",
            visibility="project",
            created_by=owner,
        )
        ReportDefinition.objects.create(
            organization=organization,
            name="Monthly cost to date",
            report_type="cost_to_date",
            description="Organization-wide cost to date.",
            visibility="organization",
            created_by=owner,
        )
        Dashboard.objects.create(
            organization=organization,
            project=project,
            name="Project executive dashboard",
            layout=[
                {"widget": "kpis", "span": 12},
                {"widget": "rfi_aging", "span": 6},
                {"widget": "task_progress", "span": 6},
            ],
            is_default=True,
            shared_with_org=True,
            created_by=owner,
        )
        collect_metrics_for_org(organization)

        application = ApiApplication.objects.create(
            organization=organization,
            name="Field Mobile",
            description="Demo field application credentials.",
            environment="development",
            scopes=["read", "write", "projects"],
            created_by=owner,
        )
        issue_credentials(application)
        WebhookSubscription.objects.create(
            organization=organization,
            application=application,
            name="Demo webhook",
            target_url="https://example.test/siteforge/webhook",
            secret=generate_webhook_secret(),
            event_types=["rfi.created", "change_order.approved", "invoice.approved"],
            created_by=owner,
        )

        notify(
            recipient=owner,
            verb="project.milestone.due",
            title="Structure topped out milestone approaching",
            body="The structure topped-out milestone is due in 90 days.",
            level="info",
            organization=organization,
            project=project,
            target_type="Milestone",
            target_id="",
        )
        notify(
            recipient=users["admin"],
            verb="rfi.overdue",
            title=f"RFI {answered_rfi.number} needs follow-up",
            body="Verify the response has been distributed to the field.",
            level="warning",
            organization=organization,
            project=project,
            target_type="RFI",
            target_id=answered_rfi.id,
        )

        self.stdout.write(self.style.SUCCESS("Seeded SiteForge demo data."))
        self.stdout.write(
            f"Organization: {organization.name} ({organization.slug})\n"
            f"Project: {project.name} ({project.number})\n"
            f"Users: {', '.join(email for email, *_ in DEMO_USERS)}\n"
            f"Password: {DEMO_PASSWORD}"
        )

    def _print_credentials(self):
        self.stdout.write(f"Demo users: {', '.join(email for email, *_ in DEMO_USERS)}")
        self.stdout.write(f"Password: {DEMO_PASSWORD}")
