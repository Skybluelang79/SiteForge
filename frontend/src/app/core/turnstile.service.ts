import { Injectable, signal } from '@angular/core';

interface TurnstileRenderOptions {
  sitekey: string;
  callback: (token: string) => void;
  'expired-callback': () => void;
  'error-callback': () => void;
  theme: 'light';
  size: 'normal';
}

interface TurnstileApi {
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string;
  reset: (widgetId?: string) => void;
}

@Injectable({ providedIn: 'root' })
export class TurnstileService {
  private readonly siteKey = (globalThis as any).__sf?.turnstileSiteKey as string | undefined;
  private widgetId: string | null = null;
  private mounted: HTMLElement | null = null;
  private scriptPromise: Promise<void> | null = null;

  readonly enabled = signal(Boolean(this.siteKey));
  readonly ready = signal(!this.siteKey);
  readonly failed = signal(false);
  readonly token = signal('');

  render(container: HTMLElement | null): void {
    if (!container) {
      return;
    }
    if (!this.siteKey) {
      this.token.set('');
      this.ready.set(true);
      return;
    }
    if (this.mounted === container && this.widgetId) {
      return;
    }
    this.mounted = container;
    this.token.set('');
    this.ready.set(false);
    this.failed.set(false);
    void this.ensureScript()
      .then(() => {
        const api = (globalThis as any).turnstile as TurnstileApi | undefined;
        if (!api || typeof api.render !== 'function') {
          this.failed.set(true);
          return;
        }
        this.widgetId = api.render(container, {
          sitekey: this.siteKey as string,
          callback: (value: string) => {
            this.token.set(value);
            this.ready.set(true);
            this.failed.set(false);
          },
          'expired-callback': () => {
            this.token.set('');
            this.ready.set(false);
          },
          'error-callback': () => {
            this.token.set('');
            this.ready.set(false);
            this.failed.set(true);
          },
          theme: 'light',
          size: 'normal',
        });
      })
      .catch(() => this.failed.set(true));
  }

  reset(): void {
    this.token.set('');
    if (!this.siteKey) {
      this.ready.set(true);
      return;
    }
    this.ready.set(false);
    const api = (globalThis as any).turnstile as TurnstileApi | undefined;
    if (api && typeof api.reset === 'function' && this.widgetId) {
      api.reset(this.widgetId);
      return;
    }
    if (this.mounted) {
      this.widgetId = null;
      this.render(this.mounted);
    }
  }

  private ensureScript(): Promise<void> {
    if (this.scriptPromise) {
      return this.scriptPromise;
    }
    const api = (globalThis as any).turnstile as TurnstileApi | undefined;
    if (api && typeof api.render === 'function') {
      this.scriptPromise = Promise.resolve();
      return this.scriptPromise;
    }
    if (typeof document === 'undefined') {
      this.scriptPromise = Promise.reject(new Error('Document unavailable'));
      return this.scriptPromise;
    }
    const existing = document.querySelector<HTMLScriptElement>('script[data-sf-turnstile="true"]');
    if (existing) {
      this.scriptPromise = new Promise<void>((resolve, reject) => {
        const loaded = (globalThis as any).turnstile as TurnstileApi | undefined;
        if (loaded && typeof loaded.render === 'function') {
          resolve();
          return;
        }
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener(
          'error',
          () => {
            this.scriptPromise = null;
            reject(new Error('Turnstile script failed to load'));
          },
          { once: true },
        );
      });
      return this.scriptPromise;
    }
    this.scriptPromise = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.dataset['sfTurnstile'] = 'true';
      script.addEventListener('load', () => {
        const loaded = (globalThis as any).turnstile as TurnstileApi | undefined;
        if (loaded && typeof loaded.render === 'function') {
          resolve();
        } else {
          this.scriptPromise = null;
          reject(new Error('Turnstile API unavailable'));
        }
      });
      script.addEventListener('error', () => {
        this.scriptPromise = null;
        reject(new Error('Turnstile script failed to load'));
      });
      document.head.appendChild(script);
    });
    return this.scriptPromise;
  }
}
