import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'sf-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly mfaStep = signal(false);
  readonly mfaToken = signal('');
  readonly mfaCode = signal('');

  submit(email: string, password: string): void {
    if (!email.trim() || !password) {
      this.error.set('Enter your email and password.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.auth.login(email.trim().toLowerCase(), password).subscribe({
      next: (response) => {
        if (response.mfa_required && response.mfa_token) {
          this.mfaToken.set(response.mfa_token);
          this.mfaStep.set(true);
          this.loading.set(false);
          return;
        }
        this.finishLogin();
      },
      error: (error) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
      },
    });
  }

  verify(code: string): void {
    if (!code.trim()) {
      this.error.set('Enter your authenticator code.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.auth.verifyMfa(this.mfaToken(), code.trim()).subscribe({
      next: () => this.finishLogin(),
      error: (error) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
      },
    });
  }

  back(): void {
    this.mfaStep.set(false);
    this.mfaToken.set('');
    this.mfaCode.set('');
    this.error.set('');
  }

  private finishLogin(): void {
    this.auth.loadContext().subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigate(['/dashboard']);
      },
      error: (error) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
      },
    });
  }
}
