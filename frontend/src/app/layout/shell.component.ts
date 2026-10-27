import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { NotificationService } from '../core/notification.service';
import { NotificationSocketService } from '../core/notification-socket.service';
import { IconComponent } from '../shared/icon.component';

interface ProjectSummary {
  id: string;
  name: string;
  code?: string;
  status?: string;
}

@Component({
  selector: 'sf-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, DatePipe, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.css',
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  readonly notifications = inject(NotificationService);
  private readonly notificationSocket = inject(NotificationSocketService);

  readonly projects = signal<ProjectSummary[]>([]);
  readonly mobileOpen = signal(false);
  readonly projectsError = signal(false);
  readonly notificationOpen = signal(false);

  readonly nav = [
    { path: '/dashboard', label: 'Overview', icon: 'home' },
    { path: '/projects', label: 'Projects', icon: 'users' },
    { path: '/documents', label: 'Documents', icon: 'file-text' },
    { path: '/drawings', label: 'Drawings', icon: 'folder' },
    { path: '/field', label: 'Field ops', icon: 'shield-check' },
    { path: '/tasks', label: 'Tasks', icon: 'check-square' },
    { path: '/tasks/board', label: 'Task board', icon: 'bar-chart' },
    { path: '/rfis', label: 'RFIs', icon: 'message-square' },
    { path: '/financials', label: 'Financials', icon: 'dollar-sign' },
    { path: '/financials/workspace', label: 'Fin workspace', icon: 'bar-chart' },
    { path: '/organization', label: 'Organization', icon: 'users' },
    { path: '/quality', label: 'Quality', icon: 'shield-check' },
    { path: '/reports', label: 'Reports', icon: 'bar-chart' },
    { path: '/integrations', label: 'Integrations', icon: 'plug' },
  ];

  ngOnInit(): void {
    this.api.list<ProjectSummary>('projects/', { page_size: 200 }).subscribe({
      next: (page) => {
        this.projects.set(page.results);
        const active = this.auth.activeProjectId();
        if (!active || !page.results.some((project) => project.id === active)) {
          this.auth.selectProject(page.results[0]?.id ?? null);
        }
      },
      error: () => this.projectsError.set(true),
    });
    this.notifications.loadUnreadCount().subscribe({ error: () => undefined });
    this.notifications.load({ page_size: 10 }).subscribe({ error: () => undefined });
    this.notificationSocket.connect();
  }

  ngOnDestroy(): void {
    this.notificationSocket.disconnect();
  }

  changeProject(value: string): void {
    this.auth.selectProject(value || null);
  }

  changeOrganization(value: string): void {
    this.auth.setOrganization(value);
    this.mobileOpen.set(false);
  }

  logout(): void {
    this.auth.logout();
  }

  toggleMobile(): void {
    this.mobileOpen.update((open) => !open);
  }

  toggleNotifications(): void {
    this.notificationOpen.update((open) => !open);
    if (this.notificationOpen()) {
      this.notifications.load({ page_size: 20 }).subscribe({ error: () => undefined });
    }
  }

  closeNotifications(): void {
    this.notificationOpen.set(false);
  }

  openNotification(notification: { id: string; read_at?: string | null }): void {
    if (!notification.read_at) {
      this.notifications.markRead(notification.id).subscribe({ error: () => undefined });
    }
    this.notificationOpen.set(false);
  }

  markAllNotificationsRead(): void {
    this.notifications.markAllRead().subscribe({ error: () => undefined });
  }

  displayName(): string {
    const user = this.auth.user();
    if (!user) {
      return 'Account';
    }
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
    return name || user.email;
  }

  initials(): string {
    return this.displayName()
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('');
  }

  activeProjectName(): string {
    const id = this.auth.activeProjectId();
    return this.projects().find((project) => project.id === id)?.name ?? 'Select project';
  }
}
