import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { IconComponent } from './icon.component';

interface PanelMessage {
  role: 'user' | 'assistant';
  content: string;
  provider?: string;
  time: string;
}

interface ChatResponse {
  conversation_id: string;
  reply: string;
  provider: string;
  model: string;
  latency_ms: number;
  suggestions: string[];
  degraded?: boolean;
}

interface ContextResponse {
  provider_configured: boolean;
  suggestions: string[];
  context: {
    scope: string;
    organization: string;
    project: { name: string } | null;
  };
}

interface ConversationSummary {
  id: string;
  project: string | null;
  title: string;
  updated_at: string;
}

interface StoredMessage {
  role: 'user' | 'assistant';
  content: string;
  provider?: string;
  created_at: string;
}

interface ConversationDetail {
  id: string;
  messages: StoredMessage[];
}

interface QuickAction {
  label: string;
  hint: string;
  prompt: string;
  icon: string;
}

@Component({
  selector: 'sf-ai-panel',
  imports: [FormsModule, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ai-panel.component.html',
  styleUrl: './ai-panel.component.css',
})
export class AiPanelComponent implements OnInit {
  readonly projectId = input<string | null>(null);

  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);

  @ViewChild('scroller') private scroller?: ElementRef<HTMLDivElement>;

  readonly messages = signal<PanelMessage[]>([]);
  readonly suggestions = signal<string[]>([]);
  readonly draft = signal('');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly providerConfigured = signal(false);
  readonly conversationId = signal<string | null>(null);
  readonly scopeLabel = signal('your workspace');
  readonly restored = signal(false);
  private readonly lastPrompt = signal('');

  readonly quickActions: QuickAction[] = [
    {
      label: 'Summarize project status',
      hint: 'Budget, schedule, open items',
      prompt:
        'Summarize the current project status, including budget, schedule and the most urgent open issues.',
      icon: 'activity',
    },
    {
      label: 'Draft an RFI response',
      hint: 'Answer the most urgent RFI',
      prompt:
        'Draft a clear, professional response to the most urgent open RFI and suggest the next action.',
      icon: 'message-square',
    },
    {
      label: 'Identify schedule risks',
      hint: 'Milestones and overdue work',
      prompt:
        'Identify schedule risks from upcoming milestones and overdue tasks, and recommend mitigations.',
      icon: 'calendar',
    },
    {
      label: 'Write a safety briefing',
      hint: 'Toolbox talk for the site team',
      prompt:
        'Write a concise safety briefing for the site team using recent incidents and open corrective actions.',
      icon: 'shield-check',
    },
  ];

  ngOnInit(): void {
    this.hydrate();
  }

  providerLabel(): string {
    return this.providerConfigured() ? 'Live provider' : 'Offline analyst';
  }

  scopeId(): string | null {
    return this.projectId() ?? this.auth.activeProjectId();
  }

  initials(): string {
    const user = this.auth.user();
    const name = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
    return (name || user?.email || 'You')
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('');
  }

  send(text?: string): void {
    const message = (text ?? this.draft()).trim();
    if (!message || this.loading()) {
      return;
    }
    this.draft.set('');
    this.messages.update((items) => [...items, this.message('user', message)]);
    this.post(message);
  }

  retry(): void {
    const message = this.lastPrompt();
    if (!message || this.loading()) {
      return;
    }
    this.post(message);
  }

  reset(): void {
    this.messages.set([]);
    this.conversationId.set(null);
    this.lastPrompt.set('');
    this.restored.set(false);
    this.error.set('');
    this.draft.set('');
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  private post(message: string): void {
    this.lastPrompt.set(message);
    this.error.set('');
    this.loading.set(true);
    this.scrollSoon();

    const body: Record<string, string> = { message };
    const projectId = this.scopeId();
    if (projectId) {
      body['project_id'] = projectId;
    }
    const conversationId = this.conversationId();
    if (conversationId) {
      body['conversation_id'] = conversationId;
    }

    this.api.post<ChatResponse>('assistant/chat/', body).subscribe({
      next: (response) => {
        this.conversationId.set(response.conversation_id);
        this.providerConfigured.set(response.provider !== 'fallback' && !response.degraded);
        this.messages.update((items) => [
          ...items,
          this.message('assistant', response.reply, response.provider),
        ]);
        this.suggestions.set(response.suggestions ?? []);
        this.loading.set(false);
        this.scrollSoon();
      },
      error: (error) => {
        this.loading.set(false);
        this.error.set(this.api.errorMessage(error));
        this.scrollSoon();
      },
    });
  }

  private hydrate(): void {
    const projectId = this.scopeId();
    const params: Record<string, string> = projectId ? { project_id: projectId } : {};
    this.api.get<ContextResponse>('assistant/context/', params).subscribe({
      next: (response) => {
        this.providerConfigured.set(response.provider_configured);
        this.suggestions.set(response.suggestions ?? []);
        this.scopeLabel.set(
          response.context.project?.name ??
            response.context.organization ??
            'your workspace',
        );
        this.restore(projectId);
      },
      error: () => {
        this.scopeLabel.set(projectId ? 'Selected project' : 'Portfolio-wide');
        this.restore(projectId);
      },
    });
  }

  private restore(projectId: string | null): void {
    this.api.get<ConversationSummary[]>('assistant/conversations/').subscribe({
      next: (conversations) => {
        if (this.messages().length || this.loading()) {
          return;
        }
        const match = conversations.find((item) => (item.project ?? null) === projectId);
        if (!match) {
          return;
        }
        this.api.get<ConversationDetail>(`assistant/conversations/${match.id}/`).subscribe({
          next: (detail) => {
            if (this.messages().length || this.loading() || !detail.messages.length) {
              return;
            }
            this.messages.set(
              detail.messages.map((item) =>
                this.message(item.role, item.content, item.provider, item.created_at),
              ),
            );
            this.conversationId.set(detail.id);
            this.restored.set(true);
            this.scrollSoon();
          },
          error: () => undefined,
        });
      },
      error: () => undefined,
    });
  }

  private message(
    role: 'user' | 'assistant',
    content: string,
    provider?: string,
    createdAt?: string,
  ): PanelMessage {
    const parsed = createdAt ? new Date(createdAt) : new Date();
    const time = Number.isNaN(parsed.getTime())
      ? new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return { role, content, provider, time };
  }

  private scrollSoon(): void {
    setTimeout(() => {
      const element = this.scroller?.nativeElement;
      if (element) {
        element.scrollTop = element.scrollHeight;
      }
    }, 40);
  }
}
