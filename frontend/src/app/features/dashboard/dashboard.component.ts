import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../shared/icon.component';
import { SitePlanComponent, SitePlanData } from './site-plan.component';

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

interface HealthDimension {
  key: string;
  label: string;
  score: number;
}

interface HealthProject {
  id: string;
  name: string;
  code?: string;
  status: string;
  score: number;
  health_status: string;
  trend: string;
  percent_complete: number;
  dimensions: HealthDimension[];
  spend_ratio: number;
  open_tasks: number;
  overdue_tasks: number;
  open_rfis: number;
  overdue_rfis: number;
  safety_incidents_90d: number;
  pending_change_orders: number;
}

interface Health {
  score: number;
  status: string;
  dimensions: HealthDimension[];
  projects: HealthProject[];
}

interface RiskInsight {
  id: string;
  severity: string;
  category: string;
  category_label: string;
  title: string;
  detail: string;
  project_id: string;
  project_name: string;
  metric: number;
  metric_label: string;
  action_label: string;
  action_route: string;
}

interface Milestone {
  id: string;
  name: string;
  due_date: string;
  status: string;
}

interface Project {
  id: string;
  name: string;
  number?: string;
  status?: string;
  city?: string;
  region?: string;
  percent_complete?: number;
  health_status?: string;
  health_score?: number;
}

interface Promotion {
  id: string;
  eyebrow: string;
  title: string;
  body: string;
  cta: string;
  route: string;
  tone: string;
}

interface DashboardResponse {
  kpis: Kpis;
  health: Health;
  risk_insights: RiskInsight[];
  site_plan: SitePlanData | null;
  milestones_due_soon: Milestone[];
  projects: Project[];
  promotions: Promotion[];
}

@Component({
  selector: 'sf-dashboard',
  imports: [RouterLink, IconComponent, SitePlanComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly data = signal<DashboardResponse | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly todayLabel = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  constructor() {
    toObservable(this.auth.activeProjectId)
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.load());
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    const project = this.auth.activeProjectId();
    this.api.get<DashboardResponse>('dashboard/', project ? { project } : {}).subscribe({
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

  healthLabel(status: string | undefined): string {
    const labels: Record<string, string> = {
      healthy: 'Healthy',
      at_risk: 'At risk',
      critical: 'Critical',
    };
    return labels[status ?? ''] ?? 'Unknown';
  }

  healthColor(status: string | undefined): string {
    const colors: Record<string, string> = {
      healthy: '#22c55e',
      at_risk: '#f59e0b',
      critical: '#ef4444',
    };
    return colors[status ?? ''] ?? '#94a3b8';
  }

  ringBackground(score: number, status: string): string {
    const angle = Math.max(0, Math.min(100, score)) * 3.6;
    return `conic-gradient(${this.healthColor(status)} ${angle}deg, #eef2f7 ${angle}deg)`;
  }

  severityLabel(severity: string): string {
    const labels: Record<string, string> = {
      critical: 'Critical',
      high: 'High',
      medium: 'Medium',
      low: 'Low',
    };
    return labels[severity] ?? severity;
  }

  scoreTone(score: number): string {
    return score >= 80 ? 'healthy' : score >= 60 ? 'at_risk' : 'critical';
  }

  trackProject(_index: number, project: Project): string {
    return project.id;
  }
}
