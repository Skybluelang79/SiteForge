import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';

import { IconComponent } from '../shared/icon.component';

interface CommandItem {
  id: string;
  label: string;
  hint: string;
  group: string;
  icon: string;
  route?: string;
  action?: string;
}

@Component({
  selector: 'sf-command-palette',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.css',
})
export class CommandPaletteComponent {
  private readonly router = inject(Router);
  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  readonly open = input(false);
  readonly close = output<void>();
  readonly action = output<string>();

  readonly query = signal('');
  readonly activeIndex = signal(0);

  private readonly commands: CommandItem[] = [
    { id: 'overview', label: 'Go to Overview', hint: 'Portfolio command center', group: 'Navigate', icon: 'home', route: '/dashboard' },
    { id: 'projects', label: 'Go to Projects', hint: 'Portfolio and project detail', group: 'Navigate', icon: 'users', route: '/projects' },
    { id: 'site-plan', label: 'Open Design Canvas', hint: 'Draw markups and details', group: 'Navigate', icon: 'edit', route: '/design/canvas' },
    { id: 'tasks', label: 'Go to Tasks', hint: 'Task list and board', group: 'Navigate', icon: 'check-square', route: '/tasks' },
    { id: 'task-board', label: 'Open Task Board', hint: 'Kanban delivery board', group: 'Navigate', icon: 'bar-chart', route: '/tasks/board' },
    { id: 'rfis', label: 'Go to RFIs', hint: 'Questions and submittals', group: 'Navigate', icon: 'message-square', route: '/rfis' },
    { id: 'financials', label: 'Open Financials', hint: 'Budget, commitments, invoices', group: 'Navigate', icon: 'dollar-sign', route: '/financials' },
    { id: 'financials-workspace', label: 'Open Financials Workspace', hint: 'Commercial control workspace', group: 'Navigate', icon: 'bar-chart', route: '/financials/workspace' },
    { id: 'quality', label: 'Open Quality', hint: 'Inspections, defects and safety', group: 'Navigate', icon: 'shield-check', route: '/quality' },
    { id: 'field', label: 'Open Field Ops', hint: 'Daily logs and observations', group: 'Navigate', icon: 'shield-check', route: '/field' },
    { id: 'documents', label: 'Open Documents', hint: 'Document library', group: 'Navigate', icon: 'file-text', route: '/documents' },
    { id: 'drawings', label: 'Open Drawings', hint: 'Drawing sets and revisions', group: 'Navigate', icon: 'folder', route: '/drawings' },
    { id: 'reports', label: 'Open Reports', hint: 'Analytics and exports', group: 'Navigate', icon: 'bar-chart', route: '/reports' },
    { id: 'integrations', label: 'Open Integrations', hint: 'API keys and webhooks', group: 'Navigate', icon: 'plug', route: '/integrations' },
    { id: 'organization', label: 'Open Organization', hint: 'Members, roles and settings', group: 'Navigate', icon: 'users', route: '/organization' },
    { id: 'profile', label: 'Open Profile', hint: 'Account, MFA and preferences', group: 'Navigate', icon: 'users', route: '/profile' },
    { id: 'copilot', label: 'Open AI Copilot', hint: 'Ask about risk, schedule and budget', group: 'Actions', icon: 'sparkles', action: 'copilot' },
    { id: 'notifications', label: 'Show Notifications', hint: 'Recent activity for your account', group: 'Actions', icon: 'bell', action: 'notifications' },
  ];

  readonly filtered = computed(() => {
    const query = this.query().trim().toLowerCase();
    if (!query) {
      return this.commands;
    }
    return this.commands.filter((command) =>
      `${command.label} ${command.hint} ${command.group}`.toLowerCase().includes(query),
    );
  });

  constructor() {
    effect(() => {
      if (this.open()) {
        this.query.set('');
        this.activeIndex.set(0);
        setTimeout(() => this.searchInput()?.nativeElement.focus());
      }
    });
  }

  onQuery(value: string): void {
    this.query.set(value);
    this.activeIndex.set(0);
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close.emit();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.activeIndex.update((index) =>
        Math.min(this.filtered().length - 1, index + 1),
      );
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.activeIndex.update((index) => Math.max(0, index - 1));
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const item = this.filtered()[this.activeIndex()];
      if (item) {
        this.run(item);
      }
    }
  }

  run(item: CommandItem): void {
    this.close.emit();
    if (item.route) {
      void this.router.navigateByUrl(item.route);
      return;
    }
    if (item.action) {
      this.action.emit(item.action);
    }
  }

  isActive(index: number): boolean {
    return this.activeIndex() === index;
  }
}
