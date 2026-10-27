import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { API_ROOT } from './auth.service';

export interface Page<T = Record<string, unknown>> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  list<T = Record<string, unknown>>(
    path: string,
    params: Record<string, string | number | boolean | null | undefined> = {},
  ): Observable<Page<T>> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        httpParams = httpParams.set(key, String(value));
      }
    });
    return this.http
      .get<Page<T> | T[]>(`${API_ROOT}/${path}`, { params: httpParams })
      .pipe(
        map((response) =>
          Array.isArray(response)
            ? { count: response.length, next: null, previous: null, results: response }
            : response,
        ),
      );
  }

  get<T>(path: string, params: Record<string, string | number> = {}): Observable<T> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      httpParams = httpParams.set(key, String(value));
    });
    return this.http.get<T>(`${API_ROOT}/${path}`, { params: httpParams });
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(`${API_ROOT}/${path}`, body);
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(`${API_ROOT}/${path}`, body);
  }

  delete<T = void>(path: string): Observable<T> {
    return this.http.delete<T>(`${API_ROOT}/${path}`);
  }

  errorMessage(error: unknown): string {
    const value = error as {
      error?: { error?: { message?: string; details?: Record<string, unknown> }; detail?: string };
    };
    return (
      value?.error?.error?.message ??
      value?.error?.detail ??
      'Something went wrong. Please try again.'
    );
  }
}
