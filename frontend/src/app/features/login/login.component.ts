import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService, CLOUDFLARE_ACCESS_ENABLED } from '../../core/auth.service';
import { TurnstileService } from '../../core/turnstile.service';
import { AdSlotComponent } from '../../shared/ad-slot.component';
import { AuthCanvasComponent } from '../../shared/auth-canvas.component';
import { SiteSceneComponent } from '../../shared/site-scene.component';

@Component({
  selector: 'sf-login',
  imports: [AdSlotComponent, AuthCanvasComponent, RouterLink, SiteSceneComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent implements AfterViewInit {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly turnstile = inject(TurnstileService);
  readonly cloudflareAccessEnabled = CLOUDFLARE_ACCESS_ENABLED;
  readonly loading = signal(false);
  readonly error = signal('');
  readonly mfaStep = signal(false);
  readonly mfaToken = signal('');
  readonly forgotMode = signal(false);
  readonly resetEmail = signal('');
  readonly resetSent = signal(false);

  @ViewChild('turnstileContainer', { static: true })
  private turnstileContainer?: ElementRef<HTMLDivElement>;

  ngAfterViewInit(): void {
    this.turnstile.render(this.turnstileContainer?.nativeElement ?? null);
  }

  submit(email: string, password: string): void {
    if (!email.trim() || !password) {
      this.error.set('Enter your email and password.');
      return;
    }
    const token = this.turnstile.token();
    if (this.turnstile.enabled() && !token) {
      this.error.set(this.turnstile.failed() ? 'Security verification could not load. Please refresh and try again.' : 'Please complete the security verification.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.turnstile.reset();
    this.auth.login(email.trim().toLowerCase(), password, token).subscribe({
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

  cloudflareAccess(): void {
    this.loading.set(true);
    this.error.set('');
    this.auth.cloudflareAccess().subscribe({
      next: (response) => {
        if (response.mfa_required && response.mfa_token) {
          this.mfaToken.set(response.mfa_token);
          this.mfaStep.set(true);
          this.loading.set(false);
          return;
        }
        this.finishLogin();
      },
      error: (error: unknown) => {
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

  openForgot(): void {
    this.forgotMode.set(true);
    this.resetSent.set(false);
    this.error.set('');
  }

  backToLogin(): void {
    this.forgotMode.set(false);
    this.resetSent.set(false);
    this.error.set('');
  }

  submitReset(email: string): void {
    const value = email.trim().toLowerCase();
    if (!value) {
      this.error.set('Enter your email address.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.api.post<{ detail?: string }>('auth/password/reset/', { email: value }).subscribe({
      next: () => {
        this.loading.set(false);
        this.resetSent.set(true);
      },
      error: (error) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
      },
    });
  }

  back(): void {
    this.mfaStep.set(false);
    this.mfaToken.set('');
    this.error.set('');
  }

  private finishLogin(): void {
    this.auth.loadContext().subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigate(['/dashboard']);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
      },
    });
  }
}
