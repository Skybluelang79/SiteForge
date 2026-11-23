import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService, TokenResponse } from '../../core/auth.service';
import { TurnstileService } from '../../core/turnstile.service';
import { AuthCanvasComponent } from '../../shared/auth-canvas.component';
import { SiteSceneComponent } from '../../shared/site-scene.component';

type SignupField = 'email' | 'first_name' | 'last_name' | 'password' | 'password_confirm';

interface SignupValues {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  password_confirm: string;
}

function readFieldErrors(error: unknown): Record<string, string> {
  const body = (error as { error?: unknown })?.error;
  if (!body || typeof body !== 'object') {
    return {};
  }
  const envelope = body as { error?: { details?: unknown }; details?: unknown };
  const source = (envelope.error?.details ?? envelope.details ?? body) as Record<string, unknown>;
  const result: Record<string, string> = {};
  Object.entries(source).forEach(([key, value]) => {
    if (Array.isArray(value) && typeof value[0] === 'string') {
      result[key] = value[0];
    } else if (typeof value === 'string') {
      result[key] = value;
    }
  });
  return result;
}

@Component({
  selector: 'sf-signup',
  imports: [AuthCanvasComponent, RouterLink, SiteSceneComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signup.component.html',
  styleUrl: './signup.component.css',
})
export class SignupComponent implements AfterViewInit {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly turnstile = inject(TurnstileService);
  readonly loading = signal(false);
  readonly submitted = signal(false);
  readonly error = signal('');
  readonly fieldErrors = signal<Record<string, string>>({});

  @ViewChild('turnstileContainer', { static: true })
  private turnstileContainer?: ElementRef<HTMLDivElement>;

  ngAfterViewInit(): void {
    this.turnstile.render(this.turnstileContainer?.nativeElement ?? null);
  }

  submit(values: SignupValues): void {
    this.submitted.set(true);
    this.error.set('');
    const payload: SignupValues = {
      email: values.email.trim().toLowerCase(),
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
      password: values.password,
      password_confirm: values.password_confirm,
    };
    if (!this.validate(payload)) {
      return;
    }
    const token = this.turnstile.token();
    if (this.turnstile.enabled() && !token) {
      this.error.set(this.turnstile.failed() ? 'Security verification could not load. Please refresh and try again.' : 'Please complete the security verification.');
      return;
    }
    this.loading.set(true);
    this.turnstile.reset();
    this.api
      .post<TokenResponse>('auth/register/', { ...payload, turnstile_token: token })
      .subscribe({
        next: (response) => {
          this.auth.applyAuthResponse(response);
          this.finishSignup();
        },
        error: (error: unknown) => {
          this.loading.set(false);
          const fields = readFieldErrors(error);
          this.fieldErrors.set({ ...this.fieldErrors(), ...fields });
          this.error.set(Object.keys(fields).length ? '' : this.api.errorMessage(error));
        },
      });
  }

  errorFor(field: SignupField): string {
    return this.fieldErrors()[field] ?? '';
  }

  clearError(field: SignupField): void {
    this.fieldErrors.update((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    this.error.set('');
  }

  private validate(values: SignupValues): boolean {
    const errors: Record<string, string> = {};
    if (!values.email) {
      errors['email'] = 'Enter your email address.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      errors['email'] = 'Enter a valid email address.';
    }
    if (!values.first_name) {
      errors['first_name'] = 'Enter your first name.';
    }
    if (!values.last_name) {
      errors['last_name'] = 'Enter your last name.';
    }
    if (!values.password) {
      errors['password'] = 'Create a password.';
    } else if (values.password.length < 8) {
      errors['password'] = 'Use at least 8 characters.';
    }
    if (!values.password_confirm) {
      errors['password_confirm'] = 'Confirm your password.';
    } else if (values.password !== values.password_confirm) {
      errors['password_confirm'] = 'Passwords do not match.';
    }
    this.fieldErrors.set(errors);
    return Object.keys(errors).length === 0;
  }

  private finishSignup(): void {
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
