import { Injectable, inject, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';

import { AuthService } from './auth.service';
import { Notification } from './notification.models';
import { NotificationService } from './notification.service';

@Injectable({ providedIn: 'root' })
export class NotificationSocketService implements OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly notificationService = inject(NotificationService);
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  readonly events$ = new Subject<unknown>();

  connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const token = this.auth.accessToken();
    if (!token) {
      return;
    }
    const cfg = (globalThis as any).__sf || {};
    let wsUrl: string;
    if (cfg.wsBase) {
      wsUrl = `${String(cfg.wsBase).replace(/\/$/, '')}/ws/notifications/?token=${encodeURIComponent(token)}`;
    } else {
      const apiRoot = String(cfg.apiRoot || '/api/v1');
      if (/^https?:/i.test(apiRoot)) {
        const u = new URL(apiRoot, window.location.origin);
        const wsProtocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${wsProtocol}//${u.host}/ws/notifications/?token=${encodeURIComponent(token)}`;
      } else {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        wsUrl = `${protocol}://${window.location.host}/ws/notifications/?token=${encodeURIComponent(token)}`;
      }
    }
    this.socket = new WebSocket(wsUrl);
    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
    };
    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.events$.next(data);
        if (data?.type === 'notification' || data?.event === 'notification.created') {
          const payload = data.payload ?? data.notification ?? data;
          if (payload?.id) {
            this.notificationService.addNotification(payload as Notification);
          } else {
            this.notificationService.incrementUnread();
            this.notificationService.loadUnreadCount().subscribe();
          }
        } else if (data?.type === 'unread_count' || data?.event === 'unread_count.updated') {
          const count = data.payload?.unread ?? data.unread;
          if (typeof count === 'number') {
            // Update via service
            this.notificationService.loadUnreadCount().subscribe();
          }
        }
      } catch {
        // ignore
      }
    };
    this.socket.onclose = () => {
      this.scheduleReconnect();
    };
    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
  }

  ping(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'ping' }));
    }
  }

  ngOnDestroy(): void {
    this.disconnect();
    this.events$.complete();
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || !this.auth.accessToken()) {
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}
