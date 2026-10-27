import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';

interface PunchListItem {
  id: string;
  description: string;
  location?: string;
  trade?: string;
  status: string;
  priority?: string;
  due_date?: string | null;
  assigned_to?: { first_name: string; last_name: string; email: string } | null;
  notes?: string;
  verified_at?: string | null;
}

interface PunchList {
  id: string;
  project: string;
  name: string;
  description?: string;
  status: string;
  assigned_to?: { first_name: string; last_name: string; email: string } | null;
  target_date?: string | null;
  items?: PunchListItem[];
  created_at: string;
}

@Component({
  selector: 'sf-punch-list-detail',
  imports: [FormsModule, DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './punch-list-detail.component.html',
  styleUrl: './punch-list-detail.component.css',
})
export class PunchListDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  readonly punchList = signal<PunchList | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly actionLoading = signal(false);
  readonly actionError = signal('');

  readonly itemDesc = signal('');
  readonly itemLocation = signal('');
  readonly itemTrade = signal('');
  readonly itemPriority = signal('medium');
  readonly itemDue = signal('');

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.load(id);
    } else {
      this.loading.set(false);
      this.error.set('Punch list not found');
    }
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.api.get<PunchList>(`punch-lists/${id}/`).subscribe({
      next: (punchList) => {
        this.punchList.set(punchList);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  addItem(): void {
    const punchList = this.punchList();
    if (!punchList || !this.itemDesc().trim()) {
      this.actionError.set('Enter a description.');
      return;
    }
    this.actionLoading.set(true);
    this.api
      .post<PunchListItem>(`punch-lists/${punchList.id}/items/`, {
        description: this.itemDesc().trim(),
        location: this.itemLocation().trim() || undefined,
        trade: this.itemTrade().trim() || undefined,
        priority: this.itemPriority(),
        due_date: this.itemDue() || undefined,
      })
      .subscribe({
        next: (item) => {
          this.punchList.update((current) =>
            current ? { ...current, items: [...(current.items ?? []), item] } : current,
          );
          this.itemDesc.set('');
          this.itemLocation.set('');
          this.itemTrade.set('');
          this.itemPriority.set('medium');
          this.itemDue.set('');
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionError.set(this.api.errorMessage(err));
          this.actionLoading.set(false);
        },
      });
  }

  closeItem(item: PunchListItem): void {
    this.actionLoading.set(true);
    this.api.patch<PunchListItem>(`punch-list-items/${item.id}/`, { status: 'closed' }).subscribe({
      next: (updated) => {
        this.punchList.update((current) => {
          if (!current) return current;
          return {
            ...current,
            items: (current.items ?? []).map((existing) => (existing.id === item.id ? updated : existing)),
          };
        });
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  displayUser(user?: { first_name: string; last_name: string; email: string } | null): string {
    if (!user) return 'Unassigned';
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
    return name || user.email;
  }
}
