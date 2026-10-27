import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ColumnConfig, FormFieldConfig, ResourcePageConfig } from './resource-config';

@Component({
  selector: 'sf-resource-list',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './resource-list.component.css',
  templateUrl: './resource-list.component.html',
})
export class ResourceListComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  readonly auth = inject(AuthService);

  readonly config = signal<ResourcePageConfig | null>(null);
  readonly items = signal<Record<string, unknown>[]>([]);
  readonly count = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly search = signal('');
  readonly searchTerm = signal('');
  readonly formOpen = signal(false);
  readonly saving = signal(false);
  readonly formError = signal('');
  readonly formValues = signal<Record<string, string>>({});
  readonly selected = signal<Record<string, unknown> | null>(null);
  readonly toast = signal('');
  readonly versions = signal<Record<string, unknown>[]>([]);
  readonly versionsLoading = signal(false);
  readonly uploadOpen = signal(false);
  readonly uploading = signal(false);
  readonly uploadError = signal('');
  readonly changeNote = signal('');
  readonly selectedFile = signal<File | null>(null);

  constructor() {
    this.route.data.subscribe((data) => {
      const config = data['resource'] as ResourcePageConfig | undefined;
      if (!config) {
        return;
      }
      this.config.set(config);
      this.items.set([]);
      this.page.set(1);
      this.search.set('');
      this.searchTerm.set('');
      this.selected.set(null);
      this.resetForm(config);
    });

    effect(() => {
      this.auth.activeProjectId();
      this.page();
      this.searchTerm();
      if (this.config()) {
        this.load();
      }
    });
  }

  load(): void {
    const config = this.config();
    if (!config) {
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.api
      .list(config.endpoint, {
        page: this.page(),
        page_size: 25,
        search: this.searchTerm() || null,
        project: this.auth.activeProjectId(),
      })
      .subscribe({
        next: (response) => {
          this.items.set(response.results);
          this.count.set(response.count);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(this.api.errorMessage(error));
          this.loading.set(false);
        },
      });
  }

  submitSearch(): void {
    this.page.set(1);
    this.searchTerm.set(this.search().trim());
  }

  clearSearch(): void {
    this.search.set('');
    this.searchTerm.set('');
    this.page.set(1);
  }

  changePage(delta: number): void {
    const next = this.page() + delta;
    if (next > 0 && (next - 1) * 25 < this.count()) {
      this.page.set(next);
    }
  }

  openForm(): void {
    const config = this.config();
    if (!config) {
      return;
    }
    this.resetForm(config);
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.formError.set('');
  }

  updateField(field: FormFieldConfig, value: string): void {
    this.formValues.update((values) => ({ ...values, [field.key]: value }));
  }

  save(): void {
    const config = this.config();
    if (!config) {
      return;
    }
    const values = this.formValues();
    const missing = (config.createFields ?? []).filter(
      (field) => field.required && !String(values[field.key] ?? '').trim(),
    );
    if (missing.length) {
      this.formError.set(`Please complete: ${missing.map((field) => field.label).join(', ')}.`);
      return;
    }
    const payload: Record<string, unknown> = {};
    Object.entries(values).forEach(([key, value]) => {
      if (value !== '') {
        payload[key] = value;
      }
    });
    const projectId = this.auth.activeProjectId();
    if (projectId) {
      payload['project'] = projectId;
    }
    this.saving.set(true);
    this.formError.set('');
    this.api.post(config.endpoint, payload).subscribe({
      next: () => {
        this.saving.set(false);
        this.formOpen.set(false);
        this.toast.set('Saved successfully.');
        this.load();
        setTimeout(() => this.toast.set(''), 3000);
      },
      error: (error) => {
        this.saving.set(false);
        this.formError.set(this.api.errorMessage(error));
      },
    });
  }

  select(row: Record<string, unknown>): void {
    this.selected.set(row);
    if (this.isDocument()) {
      this.loadVersions(row['id'] as string);
    } else {
      this.versions.set([]);
    }
  }

  closeDetail(): void {
    this.selected.set(null);
    this.versions.set([]);
    this.uploadOpen.set(false);
    this.uploadError.set('');
    this.changeNote.set('');
    this.selectedFile.set(null);
  }

  display(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (typeof value === 'object') {
      const record = value as Record<string, unknown>;
      return String(
        record['full_name'] ?? record['name'] ?? record['title'] ?? record['email'] ?? record['id'] ?? '—',
      );
    }
    return String(value);
  }

  cell(row: Record<string, unknown>, column: ColumnConfig): string {
    const value = row[column.key];
    if (column.type === 'date' && value) {
      const date = new Date(String(value));
      if (!Number.isNaN(date.getTime())) {
        return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
      }
    }
    if (column.type === 'money' && value !== null && value !== undefined) {
      const number = Number(value);
      if (!Number.isNaN(number)) {
        return new Intl.NumberFormat(undefined, {
          style: 'currency',
          currency: 'USD',
          maximumFractionDigits: 0,
        }).format(number);
      }
    }
    if (column.type === 'number' && value !== null && value !== undefined) {
      return `${value}%`;
    }
    return this.display(value);
  }

  statusClass(value: unknown): string {
    const text = String(value ?? '').toLowerCase();
    if (['approved', 'passed', 'done', 'closed', 'completed', 'issued'].includes(text)) return 'ok';
    if (['rejected', 'failed', 'overdue', 'blocked', 'critical'].includes(text)) return 'danger';
    if (['in_progress', 'under_review', 'submitted', 'investigating', 'pending', 'scheduled'].includes(text)) return 'warn';
    return 'neutral';
  }

  detailEntries(): Array<{ key: string; label: string; value: string }> {
    const row = this.selected();
    if (!row) {
      return [];
    }
    return Object.entries(row)
      .filter(([key]) => key !== 'id')
      .map(([key, value]) => ({
        key,
        label: key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
        value: this.display(value),
      }));
  }

  totalPages(): number {
    return Math.max(1, Math.ceil(this.count() / 25));
  }

  private   resetForm(config: ResourcePageConfig): void {
    const values: Record<string, string> = {};
    (config.createFields ?? []).forEach((field) => {
      values[field.key] = field.type === 'select' ? (field.options?.[0]?.value ?? '') : '';
    });
    this.formValues.set(values);
    this.formError.set('');
  }

  isDocument(): boolean {
    const cfg = this.config();
    return cfg?.endpoint === 'documents/' || cfg?.endpoint === 'drawings/';
  }

  openUpload(): void {
    this.uploadOpen.set(true);
    this.uploadError.set('');
    this.changeNote.set('');
    this.selectedFile.set(null);
  }

  closeUpload(): void {
    this.uploadOpen.set(false);
    this.uploadError.set('');
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.selectedFile.set(file);
  }

  loadVersions(id: string): void {
    this.versionsLoading.set(true);
    this.api.get<Record<string, unknown>[]>(`documents/${id}/versions/`).subscribe({
      next: (versions) => {
        this.versions.set(versions);
        this.versionsLoading.set(false);
      },
      error: () => {
        this.versions.set([]);
        this.versionsLoading.set(false);
      },
    });
  }

  uploadVersion(): void {
    const row = this.selected();
    const file = this.selectedFile();
    if (!row || !file) {
      this.uploadError.set('Select a file to upload.');
      return;
    }
    this.uploading.set(true);
    this.uploadError.set('');
    const formData = new FormData();
    formData.append('file', file);
    if (this.changeNote().trim()) {
      formData.append('change_note', this.changeNote().trim());
    }
    this.api.post<Record<string, unknown>>(`documents/${row['id']}/versions/`, formData).subscribe({
      next: () => {
        this.uploading.set(false);
        this.uploadOpen.set(false);
        this.loadVersions(row['id'] as string);
        this.load();
        this.toast.set('Version uploaded.');
        setTimeout(() => this.toast.set(''), 3000);
      },
      error: (err) => {
        this.uploading.set(false);
        this.uploadError.set(this.api.errorMessage(err));
      },
    });
  }

  downloadDocument(): void {
    const row = this.selected();
    if (!row) return;
    const token = this.auth.accessToken();
    const org = this.auth.activeOrganizationId();
    const url = `/api/v1/documents/${row['id']}/download/`;
    fetch(url, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(org ? { 'X-Organization-Id': org } : {}),
      },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const a = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        a.href = objectUrl;
        a.download = (row['title'] as string) || 'document';
        a.click();
        URL.revokeObjectURL(objectUrl);
      })
      .catch(() => this.toast.set('Download failed'));
  }
}

