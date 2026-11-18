import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  Input,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';

import { AssistantUiService } from '../core/assistant-ui.service';
import { AuthService } from '../core/auth.service';
import { IconComponent } from './icon.component';

interface PaletteProject {
  id: string;
  name: string;
  number?: string;
  status?: string;
}

interface Command {
  id: string;
  label: string;
  hint: string;
  icon: string;
  group: string;
  keywords?: string;
  run: () => void;
}

const NAVIGATION: Array<Omit<Command, 'run'> & { path: string }> = [
  { id: 'nav-dashboard', label: 'Open dashboard', hint: 'Portfolio overview', icon: 'home', group: 'Go to', path: '/dashboard' },
  { id: 'nav-projects', label: 'Open projects', hint: 'Project portfolio', icon: 'building', group: 'Go to', path: '/projects' },
  { id: 'nav-tasks', label: 'Open tasks', hint: 'Delivery register', icon: 'check-square', group: 'Go to', path: '/tasks' },
  { id: 'nav-board', label: 'Open task board', hint: 'Kanban workflow', icon: 'bar-chart', group: 'Go to', path: '/tasks/board' },
  { id: 'nav-rfis', label: 'Open RFIs', hint: 'Information control', icon: 'message-square', group: 'Go to', path: '/rfis' },
  { id: 'nav-financials', label: 'Open financials', hint: 'Commercial register', icon: 'dollar-sign', group: 'Go to', path: '/financials' },
  { id: 'nav-workspace', label: 'Open finance workspace', hint: 'Budgets and change orders', icon: 'trending-up', group: 'Go to', path: '/financials/workspace' },
  { id: 'nav-quality', label: 'Open quality & safety', hint: 'Inspections and defects', icon: 'shield-check', group: 'Go to', path: '/quality' },
  { id: 'nav-field', label: 'Open field operations', hint: 'Daily reports and logs', icon: 'calendar', group: 'Go to', path: '/field' },
  { id: 'nav-documents', label: 'Open documents', hint: 'Controlled documents', icon: 'file-text', group: 'Go to', path: '/documents' },
  { id: 'nav-drawings', label: 'Open drawings', hint: 'Drawing register', icon: 'folder', group: 'Go to', path: '/drawings' },
  { id: 'nav-reports', label: 'Open reports', hint: 'Analytics and exports', icon: 'bar-chart', group: 'Go to', path: '/reports' },
  { id: 'nav-org', label: 'Open organization', hint: 'Team and roles', icon: 'users', group: 'Go to', path: '/organization' },
];

@Component({
  selector: 'sf-command-palette',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.css',
})
export class CommandPaletteComponent {
  @Input() projects: PaletteProject[] = [];

  @ViewChild('search') private search?: ElementRef<HTMLInputElement>;

  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly assistant = inject(AssistantUiService);

  readonly open = signal(false);
  readonly query = signal('');
  readonly cursor = signal(0);

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    const trigger = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
    if (trigger) {
      event.preventDefault();
      this.toggle();
      return;
    }
    if (!this.open()) {
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.move(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.move(-1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const command = this.results()[this.cursor()];
      if (command) {
        this.run(command);
      }
    }
  }

  toggle(): void {
    if (this.open()) {
      this.close();
      return;
    }
    this.query.set('');
    this.cursor.set(0);
    this.open.set(true);
    setTimeout(() => this.search?.nativeElement.focus());
  }

  close(): void {
    this.open.set(false);
  }

  updateQuery(value: string): void {
    this.query.set(value);
    this.cursor.set(0);
  }

  move(delta: number): void {
    const total = this.results().length;
    if (!total) {
      return;
    }
    this.cursor.set((this.cursor() + delta + total) % total);
  }

  results(): Command[] {
    const needle = this.query().trim().toLowerCase();
    return this.commands().filter((command) => {
      if (!needle) {
        return true;
      }
      return `${command.label} ${command.hint} ${command.group} ${command.keywords ?? ''}`
        .toLowerCase()
        .includes(needle);
    });
  }

  run(command: Command): void {
    this.close();
    command.run();
  }

  private commands(): Command[] {
    const navigation: Command[] = NAVIGATION.map((command) => ({
      id: command.id,
      label: command.label,
      hint: command.hint,
      icon: command.icon,
      group: command.group,
      keywords: command.keywords,
      run: () => void this.router.navigate([command.path]),
    }));

    const ai: Command[] = [
      {
        id: 'ai-briefing',
        label: 'Ask Copilot for a daily briefing',
        hint: 'Live workspace summary',
        icon: 'sparkles',
        group: 'Copilot',
        keywords: 'ai assistant summary status',
        run: () => this.assistant.ask('Give me a daily briefing for the leadership team.'),
      },
      {
        id: 'ai-risks',
        label: 'Ask Copilot what needs attention',
        hint: 'Risks, overdue items and exposure',
        icon: 'alert-triangle',
        group: 'Copilot',
        keywords: 'ai assistant risk overdue safety quality',
        run: () => this.assistant.ask('What are the biggest risks and what should we focus on this week?'),
      },
      {
        id: 'ai-commercial',
        label: 'Ask Copilot about the commercial position',
        hint: 'Budget, commitments and change orders',
        icon: 'dollar-sign',
        group: 'Copilot',
        keywords: 'ai assistant budget cost change order',
        run: () => this.assistant.ask('Summarise the commercial position and any pending change orders.'),
      },
    ];

    const projects: Command[] = this.projects.map((project) => ({
      id: `project-${project.id}`,
      label: project.name,
      hint: `${project.number || 'No number'} Â· ${project.status ?? 'active'}`,
      icon: 'building',
      group: 'Projects',
      keywords: project.number ?? '',
      run: () => {
        this.auth.selectProject(project.id);
        void this.router.navigate(['/projects', project.id]);
      },
    }));

    return [...ai, ...projects, ...navigation];
  }
}

