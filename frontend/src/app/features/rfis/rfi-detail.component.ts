import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';

interface UserSummary {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
}

interface RfiComment {
  id: string;
  author?: UserSummary;
  body: string;
  is_official: boolean;
  created_at: string;
}

interface Rfi {
  id: string;
  project: string;
  number: string;
  subject: string;
  question: string;
  official_response?: string | null;
  status: string;
  priority: string;
  due_date?: string | null;
  assigned_to?: UserSummary | null;
  ball_in_court?: UserSummary | null;
  created_by?: UserSummary | null;
  comments?: RfiComment[];
  created_at: string;
  updated_at: string;
}

@Component({
  selector: 'sf-rfi-detail',
  imports: [DatePipe, RouterLink, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './rfi-detail.component.html',
  styleUrl: './rfi-detail.component.css',
})
export class RfiDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  readonly rfi = signal<Rfi | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly commentBody = signal('');
  readonly responseBody = signal('');
  readonly responseStatus = signal<'answered' | 'closed'>('answered');
  readonly actionLoading = signal(false);
  readonly actionError = signal('');

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.load(id);
    } else {
      this.loading.set(false);
      this.error.set('RFI not found');
    }
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.api.get<Rfi>(`rfis/${id}/`).subscribe({
      next: (rfi) => {
        this.rfi.set(rfi);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  addComment(): void {
    const rfi = this.rfi();
    if (!rfi || !this.commentBody().trim()) {
      return;
    }
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api.post<RfiComment>(`rfis/${rfi.id}/comments/`, { body: this.commentBody().trim() }).subscribe({
      next: (comment) => {
        this.rfi.update((current) =>
          current ? { ...current, comments: [comment, ...(current.comments ?? [])] } : current,
        );
        this.commentBody.set('');
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  respond(): void {
    const rfi = this.rfi();
    if (!rfi || !this.responseBody().trim()) {
      this.actionError.set('Enter an official response.');
      return;
    }
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api.post<Rfi>(`rfis/${rfi.id}/respond/`, { official_response: this.responseBody().trim(), status: this.responseStatus() }).subscribe({
      next: (updated) => {
        this.rfi.set(updated);
        this.responseBody.set('');
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  close(): void {
    const rfi = this.rfi();
    if (!rfi) return;
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api.post<Rfi>(`rfis/${rfi.id}/close/`, {}).subscribe({
      next: (updated) => {
        this.rfi.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  displayUser(user?: UserSummary | null): string {
    if (!user) return '—';
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
    return name || user.email;
  }
}
