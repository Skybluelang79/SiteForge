import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';

@Component({
  selector: 'sf-reset-password',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.css',
})
export class ResetPasswordComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);

  readonly token = signal(this.route.snapshot.queryParamMap.get('token') ?? '');
  readonly password = signal('');
  readonly confirm = signal('');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly success = signal(false);

  submit(): void {
    if (!this.token().trim()) {
      this.error.set('Reset token is missing.');
      return;
    }
    if (!this.password()) {
      this.error.set('Enter a new password.');
      return;
    }
    if (this.password() !== this.confirm()) {
      this.error.set('Passwords do not match.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.api
      .post<{ detail?: string }>('auth/password/reset/confirm/', {
        token: this.token().trim(),
        new_password: this.password(),
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.success.set(true);
          this.password.set('');
          this.confirm.set('');
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(this.api.errorMessage(err));
        },
      });
  }
}
