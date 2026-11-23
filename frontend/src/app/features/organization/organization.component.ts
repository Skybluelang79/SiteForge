import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

interface FeatureEntry {
  key: string;
  value: boolean;
}

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

  readonly tab = signal<'members' | 'invitations' | 'features'>('members');
  readonly members = signal<Record<string, unknown>[]>([]);
  readonly invitations = signal<Record<string, unknown>[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly inviteEmail = signal('');
  readonly inviteRole = signal('member');
  readonly inviting = signal(false);
  readonly inviteError = signal('');
  readonly inviteSuccess = signal(false);

  readonly features = signal<FeatureEntry[]>([]);
  readonly featuresLoading = signal(false);
  readonly featuresError = signal('');
  readonly featuresSaving = signal(false);
  readonly featuresSaved = signal(false);
  readonly newFeatureKey = signal('');

  constructor() {
    effect(() => {
      this.auth.activeOrganizationId();
      this.load();
      this.loadFeatures();
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<Record<string, unknown>>('organizations/memberships/', { page_size: 200 }).subscribe({
      next: (page) => {
        this.members.set(page.results);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
    this.api.list<Record<string, unknown>>('organizations/invitations/', { page_size: 200 }).subscribe({
      next: (page) => this.invitations.set(page.results),
      error: () => undefined,
    });
  }

  loadFeatures(): void {
    const orgId = this.auth.activeOrganizationId();
    if (!orgId) return;
    this.featuresLoading.set(true);
    this.featuresError.set('');
    this.api.get<{ flags?: Record<string, unknown> }>(`organizations/${orgId}/features/`).subscribe({
      next: (data) => {
        const flags = data?.flags && typeof data.flags === 'object' ? data.flags : {};
        const entries = Object.entries(flags)
          .map(([key, value]) => ({ key, value: Boolean(value) }))
          .sort((a, b) => a.key.localeCompare(b.key));
        this.features.set(entries);
        this.featuresLoading.set(false);
      },
      error: (err) => {
        this.featuresError.set(this.api.errorMessage(err));
        this.featuresLoading.set(false);
      },
    });
  }

  toggleFeature(key: string): void {
    this.features.update((list) =>
      list.map((f) => (f.key === key ? { ...f, value: !f.value } : f)),
    );
    this.featuresSaved.set(false);
  }

  addFeature(): void {
    const key = this.newFeatureKey().trim();
    if (!key) return;
    if (this.features().some((f) => f.key === key)) {
      this.featuresError.set('Feature flag already exists.');
      return;
    }
    this.featuresError.set('');
    this.features.update((list) => [...list, { key, value: false }].sort((a, b) => a.key.localeCompare(b.key)));
    this.newFeatureKey.set('');
    this.featuresSaved.set(false);
  }

  removeFeature(key: string): void {
    this.features.update((list) => list.filter((f) => f.key !== key));
    this.featuresSaved.set(false);
  }

  saveFeatures(): void {
    const orgId = this.auth.activeOrganizationId();
    if (!orgId) return;
    this.featuresSaving.set(true);
    this.featuresError.set('');
    const flags: Record<string, boolean> = {};
    for (const entry of this.features()) {
      flags[entry.key] = entry.value;
    }
    this.api.patch(`organizations/${orgId}/features/`, { flags }).subscribe({
      next: (data) => {
        const saved = (data as { flags?: Record<string, unknown> })?.flags ?? {};
        const entries = Object.entries(saved)
          .map(([key, value]) => ({ key, value: Boolean(value) }))
          .sort((a, b) => a.key.localeCompare(b.key));
        this.features.set(entries);
        this.featuresSaving.set(false);
        this.featuresSaved.set(true);
        setTimeout(() => this.featuresSaved.set(false), 3000);
      },
      error: (err) => {
        this.featuresSaving.set(false);
        this.featuresError.set(this.api.errorMessage(err));
      },
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
      .post('organizations/invitations/', { email: this.inviteEmail().trim(), role_code: this.inviteRole() })
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
    this.api.post(`organizations/invitations/${invitation['id']}/revoke/`, {}).subscribe({
      next: () => this.load(),
      error: (err) => this.error.set(this.api.errorMessage(err)),
    });
  }
}
