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
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { IconComponent } from '../shared/icon.component';

interface CopilotAction {
  label: string;
  route: string;
}

interface CopilotMessage {
  id: string;
  role: 'assistant' | 'user';
  text: string;
  at: Date;
  actions?: CopilotAction[];
}

interface QueuedPrompt {
  id: string;
  text: string;
  status: 'queued' | 'running' | 'done' | 'error';
  at: Date;
}

interface AssistantResponse {
  reply: string;
  provider: string;
  model: string | null;
  degraded: boolean;
  actions: CopilotAction[];
  suggested_prompts: string[];
}

interface CopilotContext {
  kpis?: {
    active_projects: number;
    overdue_tasks: number;
    overdue_rfis: number;
    open_submittals: number;
    safety_incidents_90d: number;
    budgeted: number;
    actual_cost: number;
    committed_cost: number;
    pending_change_orders: number;
  };
  health?: {
    score: number;
    status: string;
    dimensions: { key: string; label: string; score: number }[];
    projects: {
      name: string;
      score: number;
      health_status: string;
      overdue_tasks: number;
      overdue_rfis: number;
    }[];
  };
  risk_insights?: { severity: string; title: string; detail: string; project_name: string }[];
  site_plan?: {
    project_name: string;
    stats: {
      open_tasks: number;
      overdue_tasks: number;
      open_rfis: number;
      percent_complete: number;
      safety_incidents_90d: number;
    };
  } | null;
}

@Component({
  selector: 'sf-copilot',
  imports: [IconComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './copilot.component.html',
  styleUrl: './copilot.component.css',
})
export class CopilotComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly scroller = viewChild<ElementRef<HTMLDivElement>>('scroller');

  readonly open = input(false);
  readonly close = output<void>();

  readonly messages = signal<CopilotMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text:
        'I am your SiteForge Copilot. I read the live portfolio dashboard to summarise health, ' +
        'flag risk, and help you plan the next move on site.',
      at: new Date(),
    },
  ]);
  readonly queue = signal<QueuedPrompt[]>([]);
  readonly prompt = signal('');
  readonly context = signal<CopilotContext | null>(null);
  readonly contextLoading = signal(false);
  readonly busy = signal(false);

  readonly suggestions = signal([
    'Summarise portfolio risk',
    'What is slipping this week?',
    'How is budget tracking?',
    'Draft a site walk checklist',
  ]);

  readonly queuedCount = computed(
    () => this.queue().filter((item) => item.status !== 'done').length,
  );

  private processing = false;

  constructor() {
    effect(() => {
      if (this.open() && !this.context() && !this.contextLoading()) {
        this.loadContext();
      }
    });

    effect(() => {
      this.open();
      this.messages();
      const element = this.scroller()?.nativeElement;
      if (element) {
        setTimeout(() => {
          element.scrollTop = element.scrollHeight;
        });
      }
    });
  }

  loadContext(): void {
    this.contextLoading.set(true);
    this.api.get<CopilotContext>('dashboard/').subscribe({
      next: (context) => {
        this.context.set(context);
        this.contextLoading.set(false);
      },
      error: () => this.contextLoading.set(false),
    });
  }

  submit(): void {
    const text = this.prompt();
    if (!text.trim()) {
      return;
    }
    this.prompt.set('');
    this.enqueue(text);
  }

  useSuggestion(text: string): void {
    this.enqueue(text);
  }

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.submit();
    }
  }

  removeQueued(id: string): void {
    this.queue.update((items) =>
      items.filter((item) => !(item.id === id && item.status === 'queued')),
    );
  }

  clearCompleted(): void {
    this.queue.update((items) => items.filter((item) => item.status !== 'done'));
  }

  statusLabel(status: QueuedPrompt['status']): string {
    const labels: Record<QueuedPrompt['status'], string> = {
      queued: 'Queued',
      running: 'Thinking',
      done: 'Answered',
      error: 'Failed',
    };
    return labels[status];
  }

  timeLabel(value: Date): string {
    return value.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  enqueue(text: string): void {
    const clean = text.trim();
    if (!clean) {
      return;
    }
    this.queue.update((items) => [
      ...items,
      { id: crypto.randomUUID(), text: clean, status: 'queued', at: new Date() },
    ]);
    this.drainQueue();
  }

  private drainQueue(): void {
    if (this.processing) {
      return;
    }
    const next = this.queue().find((item) => item.status === 'queued');
    if (!next) {
      this.busy.set(false);
      return;
    }

    this.processing = true;
    this.busy.set(true);
    this.queue.update((items) =>
      items.map((item) => (item.id === next.id ? { ...item, status: 'running' } : item)),
    );
    this.messages.update((items) => [
      ...items,
      { id: crypto.randomUUID(), role: 'user', text: next.text, at: new Date() },
    ]);

    const history = this.messages()
      .filter((message) => message.id !== 'welcome')
      .slice(-10)
      .map((message) => ({ role: message.role, content: message.text }));

    this.api
      .post<AssistantResponse>('assistant/chat/', {
        messages: history,
        project_id: this.auth.activeProjectId(),
      })
      .subscribe({
        next: (response) => {
          this.messages.update((items) => [
            ...items,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              text: response.reply,
              at: new Date(),
              actions: response.actions,
            },
          ]);
          if (response.suggested_prompts?.length) {
            this.suggestions.set(response.suggested_prompts);
          }
          this.finish(next.id, 'done');
        },
        error: (error) => {
          const detail = this.api.errorMessage(error);
          this.messages.update((items) => [
            ...items,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              text:
                `I could not reach the copilot service. ${detail} ` +
                'The dashboard remains available while you retry.',
              at: new Date(),
            },
          ]);
          this.finish(next.id, 'error');
        },
      });
  }

  private finish(id: string, status: 'done' | 'error'): void {
    this.queue.update((items) =>
      items.map((item) => (item.id === id ? { ...item, status } : item)),
    );
    this.processing = false;
    this.drainQueue();
  }
}
