import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'sf-organization',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './organization.component.html',
  styleUrl: './organization.component.css',
})
export class OrganizationComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly tab = signal<'members' | 'invitations'>('members');
  readonly members = signal<Record<string, unknown>[]>([]);
  readonly invitations = signal<Record<string, unknown>[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly inviteEmail = signal('');
  readonly inviteRole = signal('member');
  readonly inviting = signal(false);
  readonly inviteError = signal('');
  readonly inviteSuccess = signal(false);

  constructor() {
    effect(() => {
      this.auth.activeOrganizationId();
      this.load();
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<Record<string, unknown>>('memberships/', { page_size: 200 }).subscribe({
      next: (page) => {
        this.members.set(page.results);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
    this.api.list<Record<string, unknown>>('invitations/', { page_size: 200 }).subscribe({
      next: (page) => this.invitations.set(page.results),
      error: () => undefined,
    });
  }

  invite(): void {
    if (!this.inviteEmail().trim()) {
      this.inviteError.set('Enter an email address.');
      return;
    }
    this.inviting.set(true);
    this.inviteError.set('');
    this.inviteSuccess.set(false);
    this.api
      .post('invitations/', { email: this.inviteEmail().trim(), role_code: this.inviteRole() })
      .subscribe({
        next: () => {
          this.inviting.set(false);
          this.inviteSuccess.set(true);
          this.inviteEmail.set('');
          this.load();
          setTimeout(() => this.inviteSuccess.set(false), 3000);
        },
        error: (err) => {
          this.inviting.set(false);
          this.inviteError.set(this.api.errorMessage(err));
        },
      });
  }

  revoke(invitation: Record<string, unknown>): void {
    this.api.post(`invitations/${invitation['id']}/revoke/`, {}).subscribe({
      next: () => this.load(),
      error: (err) => this.error.set(this.api.errorMessage(err)),
    });
  }
}
