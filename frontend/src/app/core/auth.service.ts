import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

export const API_ROOT = '/api/v1';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name?: string;
  phone?: string;
  title?: string;
  timezone?: string;
  mfa_enabled?: boolean;
}

export interface Membership {
  id: string;
  organization: string;
  organization_name: string;
  organization_slug: string;
  role_code: string;
  role?: string;
  title?: string;
  is_owner: boolean;
  is_active: boolean;
}

export interface AuthContext {
  user: User;
  memberships: Membership[];
  active_organization_id: string;
  permissions: string[];
}

interface TokenResponse {
  access: string;
  refresh: string;
  user: User;
  mfa_required?: boolean;
  mfa_token?: string;
}

const ACCESS_KEY = 'sf_access';
const REFRESH_KEY = 'sf_refresh';
const USER_KEY = 'sf_user';
const ORG_KEY = 'sf_org';
const PROJECT_KEY = 'sf_project';

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly accessToken = signal<string | null>(localStorage.getItem(ACCESS_KEY));
  readonly context = signal<AuthContext | null>(null);
  readonly user = signal<User | null>(readJson<User>(USER_KEY));
  readonly loading = signal(false);
  readonly activeProjectId = signal<string | null>(localStorage.getItem(PROJECT_KEY));
  readonly activeOrganizationId = signal<string | null>(localStorage.getItem(ORG_KEY));

  readonly isAuthenticated = computed(() => Boolean(this.accessToken()));
  readonly memberships = computed(() => this.context()?.memberships ?? []);
  readonly permissions = computed(() => new Set(this.context()?.permissions ?? []));
  readonly organizationName = computed(
    () => this.memberships().find((m) => m.organization === this.activeOrganizationId())?.organization_name ?? 'Workspace',
  );

  login(email: string, password: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${API_ROOT}/auth/login/`, { email, password })
      .pipe(tap((response) => this.persistTokens(response)));
  }

  verifyMfa(mfaToken: string, code: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${API_ROOT}/auth/mfa/verify/`, { mfa_token: mfaToken, code })
      .pipe(tap((response) => this.persistTokens(response)));
  }

  loadContext(): Observable<AuthContext> {
    this.loading.set(true);
    return this.http.get<AuthContext>(`${API_ROOT}/auth/context/`).pipe(
      tap({
        next: (context) => {
          this.context.set(context);
          this.user.set(context.user);
          localStorage.setItem(USER_KEY, JSON.stringify(context.user));
          if (!this.activeOrganizationId()) {
            this.setOrganization(context.active_organization_id, false);
          }
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      }),
    );
  }

  setOrganization(organizationId: string, reload = true): void {
    this.activeOrganizationId.set(organizationId);
    localStorage.setItem(ORG_KEY, organizationId);
    if (reload && this.accessToken()) {
      this.loadContext().subscribe({ error: () => undefined });
    }
  }

  selectProject(projectId: string | null): void {
    this.activeProjectId.set(projectId);
    if (projectId) {
      localStorage.setItem(PROJECT_KEY, projectId);
    } else {
      localStorage.removeItem(PROJECT_KEY);
    }
  }

  hasPermission(permission: string): boolean {
    return this.permissions().has(permission);
  }

  refreshAccessToken(): Promise<string | null> {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!refresh) {
      return Promise.resolve(null);
    }
    return fetch(`${API_ROOT}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error('refresh_failed');
        }
        const data = (await response.json()) as { access: string; refresh?: string };
        localStorage.setItem(ACCESS_KEY, data.access);
        if (data.refresh) {
          localStorage.setItem(REFRESH_KEY, data.refresh);
        }
        this.accessToken.set(data.access);
        return data.access;
      })
      .catch(() => {
        this.clearSession();
        return null;
      });
  }

  logout(): void {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (refresh) {
      this.http.post(`${API_ROOT}/auth/logout/`, { refresh }).subscribe({ error: () => undefined });
    }
    this.clearSession();
    void this.router.navigate(['/login']);
  }

  private persistTokens(response: TokenResponse): void {
    if (response.mfa_required || !response.access) {
      return;
    }
    localStorage.setItem(ACCESS_KEY, response.access);
    localStorage.setItem(REFRESH_KEY, response.refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));
    localStorage.removeItem(ORG_KEY);
    this.accessToken.set(response.access);
    this.activeOrganizationId.set(null);
    this.user.set(response.user);
  }

  private clearSession(): void {
    [ACCESS_KEY, REFRESH_KEY, USER_KEY, ORG_KEY, PROJECT_KEY].forEach((key) => localStorage.removeItem(key));
    this.accessToken.set(null);
    this.context.set(null);
    this.user.set(null);
    this.activeOrganizationId.set(null);
    this.activeProjectId.set(null);
  }
}
