import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../core/api.service';
import { AssistantUiService } from '../core/assistant-ui.service';
import { AuthService } from '../core/auth.service';
import { IconComponent } from './icon.component';

interface ChatMessage {
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
}

interface ContextResponse {
  suggestions: string[];
  provider_configured: boolean;
  context: {
    scope: string;
    organization: string;
    project: { name: string } | null;
  };
}

@Component({
  selector: 'sf-ai-assistant',
  imports: [FormsModule, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ai-assistant.component.html',
  styleUrl: './ai-assistant.component.css',
})
export class AiAssistantComponent {
  readonly ui = inject(AssistantUiService);
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);

  @ViewChild('scroller') private scroller?: ElementRef<HTMLDivElement>;

  readonly messages = signal<ChatMessage[]>([]);
  readonly suggestions = signal<string[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly providerConfigured = signal(false);
  readonly conversationId = signal<string | null>(null);
  readonly draft = signal('');
  readonly hydrated = signal(false);
  readonly scopeLabel = signal('your workspace');

  constructor() {
    effect(() => {
      if (this.ui.open() && !this.hydrated()) {
        this.hydrate();
      }
    });
    effect(() => {
      if (!this.ui.open() || this.loading()) {
        return;
      }
      const prompt = this.ui.consumePrompt();
      if (prompt) {
        queueMicrotask(() => this.send(prompt));
      }
    });
  }

  providerLabel(): string {
    return this.providerConfigured() ? 'Live model' : 'Offline analyst';
  }

  toggle(): void {
    this.ui.toggle();
  }

  close(): void {
    this.ui.hide();
  }

  send(text?: string): void {
    const message = (text ?? this.draft()).trim();
    if (!message || this.loading()) {
      return;
    }
    this.draft.set('');
    this.error.set('');
    this.messages.update((items) => [...items, this.message('user', message)]);
    this.loading.set(true);
    this.scrollSoon();

    const body: Record<string, string> = { message };
    const projectId = this.auth.activeProjectId();
    if (projectId) {
      body['project_id'] = projectId;
    }
    if (this.conversationId()) {
      body['conversation_id'] = this.conversationId() as string;
    }

    this.api.post<ChatResponse>('assistant/chat/', body).subscribe({
      next: (response) => {
        this.conversationId.set(response.conversation_id);
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

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  clear(): void {
    this.messages.set([]);
    this.conversationId.set(null);
    this.hydrate();
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

  private hydrate(): void {
    const projectId = this.auth.activeProjectId();
    const params: Record<string, string> = projectId ? { project_id: projectId } : {};
    this.api.get<ContextResponse>('assistant/context/', params).subscribe({
      next: (response) => {
        this.providerConfigured.set(response.provider_configured);
        this.suggestions.set(response.suggestions ?? []);
        this.scopeLabel.set(
          response.context.project?.name ?? response.context.organization ?? 'your workspace',
        );
        this.hydrated.set(true);
        if (!this.messages().length) {
          const name = this.auth.user()?.first_name || 'there';
          this.messages.set([
            this.message(
              'assistant',
              `Hi ${name}. I'm SiteForge Copilot. I have the latest numbers for ${this.scopeLabel()} — budget, schedule, RFIs, quality and safety. What do you want to know?`,
            ),
          ]);
        }
      },
      error: () => {
        this.hydrated.set(true);
        this.suggestions.set([
          'Give me a portfolio health summary.',
          'What is overdue across all projects?',
        ]);
      },
    });
  }

  private message(role: 'user' | 'assistant', content: string, provider?: string): ChatMessage {
    return {
      role,
      content,
      provider,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
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
