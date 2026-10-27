import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

interface Project {
  id: string;
  name: string;
  number: string;
  status: string;
  project_type?: string;
  city?: string;
  region?: string;
  start_date?: string;
  target_completion_date?: string;
  contract_value?: string;
  currency?: string;
  member_count?: number;
  project_manager?: { full_name?: string; email?: string };
}

interface ProjectDraft {
  name: string;
  number: string;
  city: string;
  region: string;
  start_date: string;
  target_completion_date: string;
  contract_value: string;
  client_name: string;
}

@Component({
  selector: 'sf-projects',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './projects.component.html',
  styleUrl: './projects.component.css',
})
export class ProjectsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly projects = signal<Project[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly search = signal('');
  readonly formOpen = signal(false);
  readonly saving = signal(false);
  readonly formError = signal('');
  readonly draft = signal<ProjectDraft>({
    name: '',
    number: '',
    city: '',
    region: '',
    start_date: '',
    target_completion_date: '',
    contract_value: '',
    client_name: '',
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .list<Project>('projects/', { page_size: 200, ordering: '-created_at' })
      .subscribe({
        next: (page) => {
          this.projects.set(page.results);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(this.api.errorMessage(error));
          this.loading.set(false);
        },
      });
  }

  filtered(): Project[] {
    const term = this.search().trim().toLowerCase();
    if (!term) {
      return this.projects();
    }
    return this.projects().filter((project) =>
      `${project.name} ${project.number} ${project.city ?? ''}`.toLowerCase().includes(term),
    );
  }

  setDraft(key: keyof ProjectDraft, value: string): void {
    this.draft.update((draft) => ({ ...draft, [key]: value }));
  }

  openForm(): void {
    this.draft.set({
      name: '',
      number: '',
      city: '',
      region: '',
      start_date: '',
      target_completion_date: '',
      contract_value: '',
      client_name: '',
    });
    this.formError.set('');
    this.formOpen.set(true);
  }

  save(): void {
    const draft = this.draft();
    if (!draft.name.trim() || !draft.number.trim()) {
      this.formError.set('Project name and number are required.');
      return;
    }
    const payload: Record<string, unknown> = {
      name: draft.name.trim(),
      number: draft.number.trim(),
      status: 'active',
    };
    (['city', 'region', 'start_date', 'target_completion_date', 'contract_value', 'client_name'] as const).forEach(
      (key) => {
        if (draft[key]) {
          payload[key] = draft[key];
        }
      },
    );
    this.saving.set(true);
    this.api.post<Project>('projects/', payload).subscribe({
      next: (project) => {
        this.saving.set(false);
        this.formOpen.set(false);
        this.auth.selectProject(project.id);
        this.load();
        void this.router.navigate(['/projects', project.id]);
      },
      error: (error) => {
        this.saving.set(false);
        this.formError.set(this.api.errorMessage(error));
      },
    });
  }

  money(value: string | undefined, currency?: string): string {
    const number = Number(value ?? 0);
    if (!number) {
      return '—';
    }
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(number);
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
}
