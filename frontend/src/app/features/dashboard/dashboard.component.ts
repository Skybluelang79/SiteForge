import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AssistantUiService } from '../../core/assistant-ui.service';
import { AuthService } from '../../core/auth.service';
import { AdSlotComponent } from '../../shared/ad-slot.component';
import { SitePlanComponent, SitePlanProject } from '../../shared/site-plan.component';
import { IconComponent } from '../../shared/icon.component';

interface Kpis {
  active_projects: number;
  total_projects: number;
  open_tasks: number;
  overdue_tasks: number;
  open_rfis: number;
  overdue_rfis: number;
  open_submittals: number;
  safety_incidents_90d: number;
  budgeted: number;
  actual_cost: number;
  committed_cost: number;
  pending_change_orders: number;
}

interface Milestone {
  id: string;
  name: string;
  due_date: string;
  status: string;
  project?: string;
}

interface Project {
  id: string;
  name: string;
  number?: string;
  status?: string;
  city?: string;
  region?: string;
  percent_complete?: number;
  risk_level?: string;
  risk_score?: number;
  overdue_items?: number;
  open_items?: number;
  contract_value?: number;
}

interface HealthSignal {
  label: string;
  value: number;
  severity: string;
  hint: string;
}

interface Risk {
  project_id: string;
  project: string;
  title: string;
  detail: string;
  category: string;
  severity: string;
}

interface DashboardResponse {
  kpis: Kpis;
  milestones_due_soon: Milestone[];
  projects: Project[];
  site_plan: SitePlanProject[];
  health: {
    score: number;
    label: string;
    headline: string;
    projects_at_risk: number;
    signals: HealthSignal[];
    risks: Risk[];
    counts: { healthy: number; watch: number; at_risk: number; critical: number };
  };
}

@Component({
  selector: 'sf-dashboard',
  imports: [RouterLink, SitePlanComponent, AdSlotComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly assistant = inject(AssistantUiService);
  readonly auth = inject(AuthService);

  readonly data = signal<DashboardResponse | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly todayLabel = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.get<DashboardResponse>('dashboard/').subscribe({
      next: (response) => {
        this.data.set(response);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(this.api.errorMessage(error));
        this.loading.set(false);
      },
    });
  }

  openCopilot(prompt?: string): void {
    if (prompt) {
      this.assistant.ask(prompt);
    } else {
      this.assistant.show();
    }
  }

  openProject(project: SitePlanProject): void {
    this.auth.selectProject(project.id);
    void this.router.navigate(['/projects', project.id]);
  }

  money(value: number | undefined): string {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(value ?? 0);
  }

  number(value: number | undefined): string {
    return new Intl.NumberFormat().format(value ?? 0);
  }

  utilization(): number {
    const kpis = this.data()?.kpis;
    if (!kpis || !kpis.budgeted) {
      return 0;
    }
    return Math.min(100, Math.round((kpis.actual_cost / kpis.budgeted) * 100));
  }

  committed(): number {
    const kpis = this.data()?.kpis;
    if (!kpis || !kpis.budgeted) {
      return 0;
    }
    return Math.min(100, Math.round((kpis.committed_cost / kpis.budgeted) * 100));
  }

  dateLabel(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  firstName(): string {
    return this.auth.user()?.first_name || this.auth.user()?.email?.split('@')[0] || 'there';
  }

  healthTone(label: string | undefined): string {
    if (label === 'critical' || label === 'at_risk') {
      return 'danger';
    }
    if (label === 'watch') {
      return 'warn';
    }
    return 'good';
  }
}
