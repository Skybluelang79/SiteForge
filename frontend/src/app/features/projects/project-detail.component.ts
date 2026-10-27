import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

interface Project {
  id: string;
  name: string;
  number: string;
  status: string;
  project_type?: string;
  description?: string;
  address_line1?: string;
  city?: string;
  region?: string;
  postal_code?: string;
  country?: string;
  start_date?: string;
  target_completion_date?: string;
  contract_value?: string;
  currency?: string;
  client_name?: string;
  project_manager?: { full_name?: string; email?: string };
  is_public?: boolean;
}

interface Summary {
  milestones: { total: number; achieved: number; overdue: number };
  tasks: { total: number; open: number; overdue: number };
  rfis: { total: number; open: number };
  budget: { budgeted: number; actual: number };
  team_size: number;
}

interface Milestone {
  id: string;
  name: string;
  due_date?: string;
  status: string;
  weight?: number;
}

interface Member {
  id: string;
  role_code: string;
  title?: string;
  is_active: boolean;
  user?: { full_name?: string; email?: string };
}

interface Activity {
  id: string;
  verb: string;
  summary: string;
  actor?: { full_name?: string; email?: string };
  created_at: string;
}

@Component({
  selector: 'sf-project-detail',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './project-detail.component.html',
  styleUrl: './project-detail.component.css',
})
export class ProjectDetailComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly id = input.required<string>();
  readonly project = signal<Project | null>(null);
  readonly summary = signal<Summary | null>(null);
  readonly milestones = signal<Milestone[]>([]);
  readonly members = signal<Member[]>([]);
  readonly activity = signal<Activity[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly tab = signal<'overview' | 'team' | 'milestones' | 'activity'>('overview');

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const id = this.id();
    this.loading.set(true);
    forkJoin({
      project: this.api.get<Project>(`projects/${id}/`),
      summary: this.api.get<Summary>(`projects/${id}/summary/`),
      members: this.api.get<Member[]>(`projects/${id}/members/`),
      milestones: this.api.list<Milestone>('milestones/', { project: id, page_size: 100 }),
      activity: this.api.get<Activity[]>(`projects/${id}/activity/`),
    }).subscribe({
      next: (result) => {
        this.project.set(result.project);
        this.summary.set(result.summary);
        this.members.set(result.members);
        this.milestones.set(result.milestones.results);
        this.activity.set(result.activity);
        this.auth.selectProject(result.project.id);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(this.api.errorMessage(error));
        this.loading.set(false);
      },
    });
  }

  money(value: string | number | undefined, currency = 'USD'): string {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(Number(value ?? 0));
  }

  date(value: string | undefined): string {
    if (!value) {
      return '—';
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  person(value?: { full_name?: string; email?: string }): string {
    return value?.full_name || value?.email || 'Unassigned';
  }

  statusClass(status: string): string {
    if (['active', 'achieved', 'done', 'passed'].includes(status)) return 'ok';
    if (['on_hold', 'blocked', 'overdue', 'failed'].includes(status)) return 'danger';
    return 'neutral';
  }
}
