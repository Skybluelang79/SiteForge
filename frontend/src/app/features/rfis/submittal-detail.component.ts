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

interface SubmittalItem {
  id: string;
  description: string;
  spec_reference?: string;
  status: string;
  review_notes?: string;
}

interface SubmittalApproval {
  id: string;
  decision: string;
  comments?: string;
  decided_at?: string;
  approver?: UserSummary;
}

interface Submittal {
  id: string;
  project: string;
  number: string;
  title: string;
  submittal_type: string;
  spec_section?: string;
  revision: string;
  status: string;
  description?: string;
  submitted_by?: UserSummary;
  reviewer?: UserSummary;
  due_date?: string | null;
  required_by?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  items?: SubmittalItem[];
  approvals?: SubmittalApproval[];
  created_at: string;
  updated_at: string;
}

@Component({
  selector: 'sf-submittal-detail',
  imports: [DatePipe, RouterLink, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './submittal-detail.component.html',
  styleUrl: './submittal-detail.component.css',
})
export class SubmittalDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  readonly submittal = signal<Submittal | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly decision = signal<'approved' | 'rejected' | 'revise_and_resubmit'>('approved');
  readonly comments = signal('');
  readonly itemDesc = signal('');
  readonly itemSpec = signal('');
  readonly actionLoading = signal(false);
  readonly actionError = signal('');

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.load(id);
    } else {
      this.loading.set(false);
      this.error.set('Submittal not found');
    }
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.api.get<Submittal>(`submittals/${id}/`).subscribe({
      next: (submittal) => {
        this.submittal.set(submittal);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  submit(): void {
    const submittal = this.submittal();
    if (!submittal) return;
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api.post<Submittal>(`submittals/${submittal.id}/submit/`, {}).subscribe({
      next: (updated) => {
        this.submittal.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  approve(): void {
    const submittal = this.submittal();
    if (!submittal) return;
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api
      .post<Submittal>(`submittals/${submittal.id}/approve/`, {
        decision: this.decision(),
        comments: this.comments(),
      })
      .subscribe({
        next: (updated) => {
          this.submittal.set(updated);
          this.comments.set('');
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionError.set(this.api.errorMessage(err));
          this.actionLoading.set(false);
        },
      });
  }

  addItem(): void {
    const submittal = this.submittal();
    if (!submittal || !this.itemDesc().trim()) return;
    this.actionLoading.set(true);
    this.actionError.set('');
    this.api
      .post<SubmittalItem>(`submittals/${submittal.id}/items/`, {
        description: this.itemDesc().trim(),
        spec_reference: this.itemSpec().trim() || undefined,
      })
      .subscribe({
        next: (item) => {
          this.submittal.update((current) =>
            current ? { ...current, items: [...(current.items ?? []), item] } : current,
          );
          this.itemDesc.set('');
          this.itemSpec.set('');
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
