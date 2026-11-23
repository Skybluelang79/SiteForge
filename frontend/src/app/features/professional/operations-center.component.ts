import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { ApiService, Page } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

interface Project {
  id: string;
  name: string;
  number?: string;
  status?: string;
}

interface Milestone {
  id: string;
  name: string;
  status: string;
  due_date?: string | null;
  achieved_date?: string | null;
}

interface Task {
  id: string;
  title: string;
  status: string;
  priority?: string;
  start_date?: string | null;
  due_date?: string | null;
  progress_percent?: number | null;
}

interface Commitment {
  id: string;
  number?: string;
  title?: string;
  vendor_name?: string;
  status?: string;
  revised_amount?: string | number | null;
  open_balance?: string | number | null;
  currency?: string;
}

interface Invoice {
  id: string;
  number?: string;
  vendor_name?: string;
  status?: string;
  net_payable?: string | number | null;
  due_date?: string | null;
  currency?: string;
}

interface Defect {
  id: string;
  title: string;
  severity?: string;
  status: string;
  due_date?: string | null;
  location?: string;
}

interface PunchItem {
  id: string;
  description: string;
  trade?: string;
  status: string;
  due_date?: string | null;
  location?: string;
}

interface Incident {
  id: string;
  number?: string;
  title: string;
  severity?: string;
  status: string;
  occurred_at?: string | null;
}

interface DocumentRecord {
  id: string;
  title: string;
  document_type?: string;
  status?: string;
  current_version?: { version_number?: number | string; original_filename?: string } | null;
  updated_at?: string;
}

interface DrawingRecord {
  id: string;
  number?: string;
  title: string;
  discipline?: string;
  status?: string;
  current_revision?: { revision_code?: string; review_status?: string } | null;
  updated_at?: string;
}

interface DailyLog {
  id: string;
  log_date: string;
  status: string;
  weather_summary?: string;
  work_activities?: string;
  labour_count?: number;
  equipment_count?: number;
}

interface ScheduleRow {
  id: string;
  title: string;
  status: string;
  start: string | null;
  due: string | null;
  progress: number;
  left: number;
  width: number;
}

interface Kpi {
  label: string;
  value: string;
  detail: string;
  tone: 'navy' | 'amber' | 'green' | 'red' | 'blue';
}

@Component({
  selector: 'sf-operations-center',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './operations-center.component.html',
  styleUrl: './operations-center.component.css',
})
export class OperationsCenterComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly projects = signal<Project[]>([]);
  readonly milestones = signal<Milestone[]>([]);
  readonly tasks = signal<Task[]>([]);
  readonly commitments = signal<Commitment[]>([]);
  readonly invoices = signal<Invoice[]>([]);
  readonly defects = signal<Defect[]>([]);
  readonly punchItems = signal<PunchItem[]>([]);
  readonly incidents = signal<Incident[]>([]);
  readonly documents = signal<DocumentRecord[]>([]);
  readonly drawings = signal<DrawingRecord[]>([]);
  readonly logs = signal<DailyLog[]>([]);
  readonly errors = signal<Record<string, string>>({});
  readonly loading = signal(true);

  private loadVersion = 0;

  readonly activeProject = computed(
    () => this.projects().find((project) => project.id === this.auth.activeProjectId()) ?? null,
  );
  readonly hasErrors = computed(() => Object.keys(this.errors()).length > 0);

  readonly kpis = computed<Kpi[]>(() => {
    const tasks = this.tasks();
    const milestones = this.milestones();
    const commitments = this.commitments();
    const invoices = this.invoices();
    const defects = this.defects();
    const punchItems = this.punchItems();
    const incidents = this.incidents();
    const logs = this.logs();

    const openTasks = tasks.filter((task) => task.status !== 'done').length;
    const overdueTasks = tasks.filter(
      (task) => task.status !== 'done' && this.isPast(task.due_date),
    ).length;
    const achieved = milestones.filter((milestone) => milestone.status === 'achieved').length;
    const overdueMilestones = milestones.filter(
      (milestone) => milestone.status !== 'achieved' && this.isPast(milestone.due_date),
    ).length;
    const openInvoices = invoices.filter(
      (invoice) => !['paid', 'void', 'cancelled'].includes(invoice.status ?? ''),
    ).length;
    const openDefects = defects.filter(
      (defect) => !['resolved', 'closed'].includes(defect.status ?? ''),
    ).length;
    const openPunch = punchItems.filter(
      (item) => !['closed', 'complete', 'completed'].includes(item.status ?? ''),
    ).length;
    const openIncidents = incidents.filter((incident) => incident.status !== 'closed').length;
    const today = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
    const recentLogs = logs.filter(
      (log) => log.log_date?.slice(0, 10) >= weekAgo && log.log_date?.slice(0, 10) <= today,
    ).length;

    return [
      {
        label: 'Projects in scope',
        value: String(this.projects().length),
        detail: this.activeProject()?.name ?? 'All accessible projects',
        tone: 'navy',
      },
      {
        label: 'Open tasks',
        value: String(openTasks),
        detail: `${overdueTasks} past due`,
        tone: overdueTasks ? 'red' : 'amber',
      },
      {
        label: 'Milestones met',
        value: `${achieved}/${milestones.length}`,
        detail: `${overdueMilestones} overdue`,
        tone: overdueMilestones ? 'amber' : 'green',
      },
      {
        label: 'Committed value',
        value: this.money(this.sum(commitments.map((commitment) => commitment.revised_amount))),
        detail: `${commitments.length} active commitments`,
        tone: 'navy',
      },
      {
        label: 'Net payable',
        value: this.money(this.sum(invoices.map((invoice) => invoice.net_payable))),
        detail: `${openInvoices} invoices in workflow`,
        tone: openInvoices ? 'amber' : 'green',
      },
      {
        label: 'Quality backlog',
        value: String(openDefects + openPunch),
        detail: `${openDefects} defects · ${openPunch} punch items`,
        tone: openDefects + openPunch ? 'red' : 'green',
      },
      {
        label: 'Open incidents',
        value: String(openIncidents),
        detail: `${incidents.length} recorded incidents`,
        tone: openIncidents ? 'red' : 'green',
      },
      {
        label: 'Field reports',
        value: String(logs.length),
        detail: `${recentLogs} logged in last 7 days`,
        tone: 'blue',
      },
    ];
  });

  readonly scheduleRows = computed<ScheduleRow[]>(() => {
    const tasks = [...this.tasks()]
      .sort((left, right) => (left.due_date ?? '9999').localeCompare(right.due_date ?? '9999'))
      .slice(0, 12);
    const times = tasks
      .flatMap((task) => [task.start_date, task.due_date])
      .filter((value): value is string => Boolean(value))
      .map((value) => new Date(value).getTime())
      .filter((value) => !Number.isNaN(value));
    const min = times.length ? Math.min(...times) : Date.now();
    const max = times.length ? Math.max(...times) : min + 14 * 86400000;
    const span = Math.max(max - min, 86400000);

    return tasks.map((task) => {
      const due = task.due_date ?? null;
      const start =
        task.start_date ??
        (due ? new Date(new Date(due).getTime() - 2 * 86400000).toISOString().slice(0, 10) : null);
      const parsedStart = start ? new Date(start).getTime() : min;
      const parsedDue = due ? new Date(due).getTime() : parsedStart + 86400000;
      const safeStart = Number.isNaN(parsedStart) ? min : parsedStart;
      const safeDue = Number.isNaN(parsedDue) ? safeStart + 86400000 : Math.max(parsedDue, safeStart);
      const left = Math.max(0, Math.min(100, ((safeStart - min) / span) * 100));
      const width = Math.max(3, Math.min(100 - left, ((safeDue - safeStart) / span) * 100));

      return {
        id: task.id,
        title: task.title,
        status: task.status,
        start,
        due,
        progress: this.progress(task),
        left,
        width,
      };
    });
  });

  constructor() {
    effect(() => {
      this.auth.activeProjectId();
      this.load();
    });
  }

  load(): void {
    const version = ++this.loadVersion;
    this.loading.set(true);
    this.errors.set({});

    const project = this.auth.activeProjectId();
    const params = { project, page_size: 200 };
    const fetch = <T>(
      key: string,
      endpoint: string,
      extra: Record<string, string | number | null> = {},
      scopeToProject = true,
    ) =>
      this.api
        .list<T>(endpoint, { ...(scopeToProject ? params : { page_size: 200 }), ...extra })
        .pipe(
          catchError((error: unknown) => {
            if (version === this.loadVersion) {
              this.errors.update((current) => ({
                ...current,
                [key]: this.api.errorMessage(error),
              }));
            }
            return of<Page<T>>({ count: 0, next: null, previous: null, results: [] });
          }),
        );

    forkJoin({
      projects: fetch<Project>('projects', 'projects/', {}, false),
      milestones: fetch<Milestone>('milestones', 'milestones/', { ordering: 'due_date' }),
      tasks: fetch<Task>('tasks', 'tasks/', { ordering: 'due_date' }),
      commitments: fetch<Commitment>('commitments', 'commitments/'),
      invoices: fetch<Invoice>('invoices', 'invoices/'),
      defects: fetch<Defect>('defects', 'defects/'),
      punchItems: fetch<PunchItem>('punchItems', 'punch-list-items/'),
      incidents: fetch<Incident>('incidents', 'safety-incidents/'),
      documents: fetch<DocumentRecord>('documents', 'documents/'),
      drawings: fetch<DrawingRecord>('drawings', 'drawings/'),
      logs: fetch<DailyLog>('logs', 'daily-logs/'),
    }).subscribe({
      next: (result) => {
        if (version !== this.loadVersion) {
          return;
        }
        this.projects.set(result.projects.results);
        this.milestones.set(result.milestones.results);
        this.tasks.set(result.tasks.results);
        this.commitments.set(result.commitments.results);
        this.invoices.set(result.invoices.results);
        this.defects.set(result.defects.results);
        this.punchItems.set(result.punchItems.results);
        this.incidents.set(result.incidents.results);
        this.documents.set(result.documents.results);
        this.drawings.set(result.drawings.results);
        this.logs.set(result.logs.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        if (version !== this.loadVersion) {
          return;
        }
        this.errors.update((current) => ({
          ...current,
          operations: this.api.errorMessage(error),
        }));
        this.loading.set(false);
      },
    });
  }

  changeProject(value: string): void {
    this.auth.selectProject(value || null);
  }

  errorFor(key: string): string | undefined {
    return this.errors()[key];
  }

  label(value?: string | null): string {
    if (!value) {
      return '—';
    }
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  date(value?: string | null): string {
    if (!value) {
      return '—';
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  shortDate(value?: string | null): string {
    if (!value) {
      return '—';
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  money(value: unknown, currency?: string): string {
    const number = Number(value);
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(Number.isFinite(number) ? number : 0);
  }

  pillClass(value?: string | null): string {
    const text = (value ?? '').toLowerCase();
    if (
      [
        'achieved',
        'approved',
        'done',
        'passed',
        'paid',
        'issued',
        'closed',
        'resolved',
        'complete',
        'completed',
        'verified',
      ].includes(text)
    ) {
      return 'ok';
    }
    if (
      [
        'critical',
        'high',
        'fatality',
        'lost_time',
        'medical',
        'property_damage',
        'overdue',
        'blocked',
        'failed',
        'rejected',
        'investigating',
      ].includes(text)
    ) {
      return 'danger';
    }
    if (
      [
        'medium',
        'first_aid',
        'corrective_action',
        'reported',
        'ready_for_review',
        'in_progress',
        'pending',
        'submitted',
        'under_review',
        'scheduled',
        'draft',
        'active',
        'open',
      ].includes(text)
    ) {
      return 'warn';
    }
    if (['low', 'near_miss', 'minor', 'informational'].includes(text)) {
      return 'info';
    }
    return 'neutral';
  }

  progress(task: Task): number {
    if (task.status === 'done') {
      return 100;
    }
    const value = Number(task.progress_percent);
    return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
  }

  documentVersion(document: DocumentRecord): string {
    const number = document.current_version?.version_number;
    return number ? `v${number}` : '—';
  }

  private sum(values: unknown[]): number {
    return values.reduce<number>((total, value) => total + (Number(value) || 0), 0);
  }

  private isPast(value?: string | null): boolean {
    if (!value) {
      return false;
    }
    return value.slice(0, 10) < new Date().toISOString().slice(0, 10);
  }
}
