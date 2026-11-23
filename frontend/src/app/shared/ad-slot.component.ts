import { ChangeDetectionStrategy, Component, Input, OnInit, inject, signal } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { IconComponent } from './icon.component';

interface Ad {
  id: string;
  name: string;
  placement: string;
  ad_type: 'house' | 'external';
  sponsor: string;
  headline: string;
  body: string;
  cta_label: string;
  link_url: string;
  image_url: string;
  html_snippet: string;
  accent: string;
}

@Component({
  selector: 'sf-ad-slot',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (ads().length) {
      @for (ad of ads(); track ad.id) {
        <aside class="ad" [class]="'ad ' + variant" [style.--accent]="ad.accent || '#f59e0b'">
          <span class="ad-label">Sponsored</span>
          @if (ad.ad_type === 'external' && ad.html_snippet) {
            <iframe
              class="external"
              [srcdoc]="safe(ad.html_snippet)"
              sandbox="allow-scripts"
              title="Sponsored content"
              loading="lazy"
            ></iframe>
          } @else {
            <a class="house" [href]="ad.link_url || '#'" target="_blank" rel="noopener" (click)="track(ad, 'click')">
              @if (ad.image_url) {
                <span class="creative" [style.background-image]="'url(' + ad.image_url + ')'"></span>
              }
              <span class="copy">
                @if (ad.sponsor) {
                  <span class="sponsor">{{ ad.sponsor }}</span>
                }
                <strong>{{ ad.headline || ad.name }}</strong>
                @if (ad.body && variant !== 'strip') {
                  <span class="body">{{ ad.body }}</span>
                }
                @if (ad.cta_label) {
                  <span class="cta">{{ ad.cta_label }} <sf-icon name="arrow-right" [size]="13" /></span>
                }
              </span>
            </a>
          }
        </aside>
      }
    } @else if (fallback) {
      <aside class="ad fallback" [class]="'ad fallback ' + variant">
        <span class="ad-label">Ad space</span>
        <a class="house" href="mailto:ads@siteforge.io?subject=Advertise%20on%20SiteForge">
          <span class="copy">
            <span class="sponsor">SiteForge network</span>
            <strong>Your brand on every jobsite.</strong>
            <span class="body">Reach owners, builders and trade partners across SiteForge. This advertisement space is available.</span>
            <span class="cta">Advertise with us <sf-icon name="arrow-right" [size]="13" /></span>
          </span>
        </a>
      </aside>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .ad {
        position: relative;
        overflow: hidden;
        border-radius: 16px;
        border: 1px solid #e4e9f0;
        background: #fff;
        min-height: 120px;
      }
      .ad ::ng-deep sf-icon {
        display: inline-block;
        vertical-align: -2px;
      }
      .ad-label {
        position: absolute;
        top: 10px;
        right: 12px;
        z-index: 2;
        font-size: 8.5px;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #94a3b8;
      }
      .house {
        display: flex;
        gap: 16px;
        padding: 22px;
        min-height: 120px;
        box-sizing: border-box;
        text-decoration: none;
        color: inherit;
        background:
          radial-gradient(120% 150% at 100% 0%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 60%),
          #fff;
      }
      .creative {
        flex: 0 0 110px;
        border-radius: 12px;
        background-size: cover;
        background-position: center;
        border: 1px solid #eef2f7;
      }
      .copy {
        display: flex;
        flex-direction: column;
        gap: 5px;
        min-width: 0;
        padding-right: 26px;
      }
      .sponsor {
        font-size: 9px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--accent);
      }
      .copy strong {
        font-family: var(--sf-font-display);
        font-size: 16px;
        letter-spacing: -0.02em;
        color: #0b1220;
      }
      .body {
        font-size: 12px;
        line-height: 1.5;
        color: #64748b;
      }
      .cta {
        margin-top: 4px;
        font-size: 12px;
        font-weight: 700;
        color: #0b1220;
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
      .external {
        width: 100%;
        min-height: 150px;
        border: 0;
        display: block;
        background: transparent;
      }
      .strip .house {
        align-items: center;
        padding: 18px 22px;
        min-height: 96px;
      }
      .strip .copy {
        padding-right: 60px;
      }
      .strip .copy strong {
        font-size: 15px;
      }
      .strip .body {
        display: none;
      }
      .inline .house {
        padding: 16px 18px;
        min-height: 96px;
      }
      .fallback {
        border-style: dashed;
        background: linear-gradient(135deg, #0b1220, #111f38);
        border-color: #1e293b;
      }
      .fallback .ad-label {
        color: #64748b;
      }
      .fallback .house {
        background: transparent;
      }
      .fallback .copy strong {
        color: #f8fafc;
      }
      .fallback .body {
        color: #94a3b8;
      }
      .fallback .cta {
        color: #fbbf24;
      }
      .fallback .sponsor {
        color: #f59e0b;
      }
      .fallback.strip .house {
        min-height: 96px;
      }
      @media (max-width: 640px) {
        .creative {
          display: none;
        }
      }
    `,
  ],
})
export class AdSlotComponent implements OnInit {
  @Input() placement = 'landing_hero';
  @Input() variant: 'hero' | 'strip' | 'card' | 'inline' = 'card';
  @Input() fallback = false;
  @Input() orgScoped = false;

  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly sanitizer = inject(DomSanitizer);

  readonly ads = signal<Ad[]>([]);

  ngOnInit(): void {
    const params: Record<string, string> = { placement: this.placement };
    if (this.orgScoped && this.auth.activeOrganizationId()) {
      params['organization'] = this.auth.activeOrganizationId() as string;
    }
    this.api.get<{ results: Ad[] }>('ads/', params).subscribe({
      next: (response) => {
        this.ads.set(response.results ?? []);
        this.ads().forEach((ad) => this.track(ad, 'impression'));
      },
      error: () => this.ads.set([]),
    });
  }

  safe(html: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  track(ad: Ad, event: 'impression' | 'click'): void {
    const key = `sf_ad_${event}_${ad.id}`;
    if (event === 'impression' && sessionStorage.getItem(key)) {
      return;
    }
    sessionStorage.setItem(key, '1');
    this.api
      .post(`ads/${ad.id}/events/`, {
        event_type: event,
        session_key: this.sessionKey(),
      })
      .subscribe({ error: () => undefined });
  }

  private sessionKey(): string {
    const existing = sessionStorage.getItem('sf_ad_session');
    if (existing) {
      return existing;
    }
    const key = Math.random().toString(36).slice(2, 12);
    sessionStorage.setItem('sf_ad_session', key);
    return key;
  }
}
