import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'sf-profile',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
})
export class ProfileComponent {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);

  readonly tab = signal<'overview' | 'security'>('overview');
  readonly mfaLoading = signal(false);
  readonly mfaError = signal('');
  readonly mfaSecret = signal('');
  readonly mfaUri = signal('');
  readonly mfaCode = signal('');
  readonly recoveryCodes = signal<string[]>([]);
  readonly showRecovery = signal(false);
  readonly passwordCurrent = signal('');
  readonly passwordNew = signal('');
  readonly passwordConfirm = signal('');
  readonly passwordLoading = signal(false);
  readonly passwordError = signal('');
  readonly passwordSuccess = signal(false);

  name(): string {
    const user = this.auth.user();
    return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || 'Account';
  }

  initials(): string {
    return this.name()
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('');
  }

  permissionLabel(permission: string): string {
    return permission.replaceAll('.', ' • ').replaceAll('_', ' ');
  }

  logout(): void {
    this.auth.logout();
  }

  startMfa(): void {
    this.mfaLoading.set(true);
    this.mfaError.set('');
    this.api.post<{ secret: string; otpauth_uri: string }>('auth/mfa/setup/', {}).subscribe({
      next: (res) => {
        this.mfaSecret.set(res.secret);
        this.mfaUri.set(res.otpauth_uri);
        this.mfaLoading.set(false);
      },
      error: (err) => {
        this.mfaError.set(this.api.errorMessage(err));
        this.mfaLoading.set(false);
      },
    });
  }

  confirmMfa(): void {
    if (!this.mfaCode().trim()) {
      this.mfaError.set('Enter the code from your authenticator app.');
      return;
    }
    this.mfaLoading.set(true);
    this.mfaError.set('');
    this.api.post<{ recovery_codes: string[] }>('auth/mfa/confirm/', { code: this.mfaCode().trim() }).subscribe({
      next: (res) => {
        this.recoveryCodes.set(res.recovery_codes || []);
        this.showRecovery.set(true);
        this.mfaSecret.set('');
        this.mfaUri.set('');
        this.mfaCode.set('');
        this.mfaLoading.set(false);
        this.auth.loadContext().subscribe();
      },
      error: (err) => {
        this.mfaError.set(this.api.errorMessage(err));
        this.mfaLoading.set(false);
      },
    });
  }

  changePassword(): void {
    if (this.passwordNew() !== this.passwordConfirm()) {
      this.passwordError.set('Passwords do not match.');
      return;
    }
    this.passwordLoading.set(true);
    this.passwordError.set('');
    this.passwordSuccess.set(false);
    this.api
      .post('auth/password/change/', {
        current_password: this.passwordCurrent(),
        new_password: this.passwordNew(),
      })
      .subscribe({
        next: () => {
          this.passwordLoading.set(false);
          this.passwordSuccess.set(true);
          this.passwordCurrent.set('');
          this.passwordNew.set('');
          this.passwordConfirm.set('');
          setTimeout(() => this.passwordSuccess.set(false), 3000);
        },
        error: (err) => {
          this.passwordLoading.set(false);
          this.passwordError.set(this.api.errorMessage(err));
        },
      });
  }
}
