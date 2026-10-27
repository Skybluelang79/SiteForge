import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ApiService, Page } from './api.service';
import { Notification, NotificationPreference, UnreadCount } from './notification.models';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly api = inject(ApiService);

  readonly notifications = signal<Notification[]>([]);
  readonly unreadCount = signal(0);
  readonly loading = signal(false);

  load(params: Record<string, string | number | boolean | null | undefined> = {}): Observable<Page<Notification>> {
    this.loading.set(true);
    return this.api.list<Notification>('notifications/', params).pipe(
      tap((page) => {
        this.notifications.set(page.results);
        this.loading.set(false);
      }),
    );
  }

  loadUnreadCount(): Observable<UnreadCount> {
    return this.api.get<UnreadCount>('notifications/unread-count/').pipe(
      tap((result) => this.unreadCount.set(result.unread)),
    );
  }

  markRead(id: string): Observable<Notification> {
    return this.api.post<Notification>(`notifications/${id}/read/`, {}).pipe(
      tap((notification) => {
        this.notifications.update((items) =>
          items.map((item) => (item.id === id ? notification : item)),
        );
        this.unreadCount.update((count) => Math.max(0, count - 1));
      }),
    );
  }

  markAllRead(): Observable<{ marked_read: number }> {
    return this.api.post<{ marked_read: number }>('notifications/read-all/', {}).pipe(
      tap((result) => {
        this.notifications.update((items) =>
          items.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })),
        );
        this.unreadCount.set(0);
      }),
    );
  }

  delete(id: string): Observable<void> {
    return this.api.delete<void>(`notifications/${id}/`).pipe(
      tap(() => {
        const wasUnread = this.notifications().find((item) => item.id === id)?.read_at == null;
        this.notifications.update((items) => items.filter((item) => item.id !== id));
        if (wasUnread) {
          this.unreadCount.update((count) => Math.max(0, count - 1));
        }
      }),
    );
  }

  getPreferences(): Observable<NotificationPreference> {
    return this.api.get<NotificationPreference>('notification-preferences/');
  }

  updatePreferences(body: Partial<NotificationPreference>): Observable<NotificationPreference> {
    return this.api.patch<NotificationPreference>('notification-preferences/', body);
  }

  incrementUnread(): void {
    this.unreadCount.update((count) => count + 1);
  }

  addNotification(notification: Notification): void {
    this.notifications.update((items) => [notification, ...items]);
    if (!notification.read_at) {
      this.unreadCount.update((count) => count + 1);
    }
  }
}
