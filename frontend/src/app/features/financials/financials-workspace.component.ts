import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

type Tab = 'cost-codes' | 'budgets' | 'commitments' | 'pos' | 'invoices' | 'change-orders';

@Component({
  selector: 'sf-financials-workspace',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './financials-workspace.component.html',
  styleUrl: './financials-workspace.component.css',
})
export class FinancialsWorkspaceComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly tab = signal<Tab>('cost-codes');
  readonly items = signal<Record<string, unknown>[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly actionLoading = signal(false);

  constructor() {
    effect(() => {
      this.auth.activeProjectId();
      this.tab();
      this.load();
    });
  }

  load(): void {
    const endpoint = this.endpoint();
    if (!endpoint) return;
    this.loading.set(true);
    this.error.set('');
    this.api
      .list<Record<string, unknown>>(endpoint, {
        project: this.auth.activeProjectId(),
        page_size: 200,
      })
      .subscribe({
        next: (page) => {
          this.items.set(page.results);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.api.errorMessage(err));
          this.loading.set(false);
        },
      });
  }

  endpoint(): string {
    switch (this.tab()) {
      case 'cost-codes':
        return 'cost-codes/';
      case 'budgets':
        return 'budgets/';
      case 'commitments':
        return 'commitments/';
      case 'pos':
        return 'purchase-orders/';
      case 'invoices':
        return 'invoices/';
      case 'change-orders':
        return 'change-orders/';
      default:
        return 'cost-codes/';
    }
  }

  approve(item: Record<string, unknown>): void {
    const id = item['id'] as string;
    let path = '';
    switch (this.tab()) {
      case 'commitments':
        path = `commitments/${id}/approve/`;
        break;
      case 'pos':
        path = `purchase-orders/${id}/approve/`;
        break;
      case 'invoices':
        path = `invoices/${id}/approve/`;
        break;
      case 'change-orders':
        path = `change-orders/${id}/approve/`;
        break;
      default:
        return;
    }
    this.actionLoading.set(true);
    this.api.post(path, {}).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.load();
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.error.set(this.api.errorMessage(err));
      },
    });
  }

  submitCo(item: Record<string, unknown>): void {
    const id = item['id'] as string;
    this.actionLoading.set(true);
    this.api.post(`change-orders/${id}/submit/`, {}).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.load();
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.error.set(this.api.errorMessage(err));
      },
    });
  }

  payInvoice(item: Record<string, unknown>): void {
    const id = item['id'] as string;
    this.actionLoading.set(true);
    this.api.post(`invoices/${id}/pay/`, { paid_amount: item['net_payable'] }).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.load();
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.error.set(this.api.errorMessage(err));
      },
    });
  }

  money(value: unknown): string {
    const num = Number(value);
    if (Number.isNaN(num)) return '—';
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num);
  }
}
