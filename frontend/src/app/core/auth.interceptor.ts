import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

let refreshInFlight: Promise<string | null> | null = null;

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const token = auth.accessToken();
  const organizationId = auth.activeOrganizationId();

  let headers = request.headers;
  if (token) {
    headers = headers.set('Authorization', `Bearer ${token}`);
  }
  if (organizationId) {
    headers = headers.set('X-Organization-Id', organizationId);
  }

  const authorized = request.clone({ headers });

  return next(authorized).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401 || !auth.accessToken()) {
        return throwError(() => error);
      }
      if (request.url.includes('/auth/refresh/') || request.url.includes('/auth/login/')) {
        return throwError(() => error);
      }
      refreshInFlight ??= auth.refreshAccessToken().finally(() => {
        refreshInFlight = null;
      });
      return from(refreshInFlight).pipe(
        switchMap((newToken) => {
          if (!newToken) {
            return throwError(() => error);
          }
          return next(
            request.clone({
              headers: headers.set('Authorization', `Bearer ${newToken}`),
            }),
          );
        }),
      );
    }),
  );
};
