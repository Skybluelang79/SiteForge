import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AssistantUiService {
  readonly open = signal(false);
  private readonly queue = signal<string[]>([]);

  show(): void {
    this.open.set(true);
  }

  hide(): void {
    this.open.set(false);
  }

  toggle(): void {
    this.open.update((value) => !value);
  }

  ask(prompt: string): void {
    const value = prompt.trim();
    if (!value) {
      return;
    }
    this.queue.update((items) => [...items, value]);
    this.open.set(true);
  }

  consumePrompt(): string | null {
    const items = this.queue();
    if (!items.length) {
      return null;
    }
    const [next, ...rest] = items;
    this.queue.set(rest);
    return next;
  }

  hasPending(): boolean {
    return this.queue().length > 0;
  }
}
