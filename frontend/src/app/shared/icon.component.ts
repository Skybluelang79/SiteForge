import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'sf-icon',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      [attr.width]="size"
      [attr.height]="size"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      @switch (name) {
        @case ('home') {
          <path d="M3 12L12 3l9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10" />
        }
        @case ('folder') {
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
        }
        @case ('file-text') {
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
        }
        @case ('check-square') {
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
        }
        @case ('message-square') {
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        }
        @case ('dollar-sign') {
          <line x1="12" y1="1" x2="12" y2="23" />
          <path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
        }
        @case ('shield-check') {
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="M9 12l2 2 4-4" />
        }
        @case ('bar-chart') {
          <line x1="12" y1="20" x2="12" y2="10" />
          <line x1="18" y1="20" x2="18" y2="4" />
          <line x1="6" y1="20" x2="6" y2="16" />
        }
        @case ('plug') {
          <path d="M12 22v-5M9 8V2M15 8V2M18 8v5a6 6 0 01-6 6 6 6 0 01-6-6V8h12z" />
        }
        @case ('users') {
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
        }
        @case ('bell') {
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
        }
        @case ('building') {
          <path d="M3 21h18M5 21V5a2 2 0 012-2h6a2 2 0 012 2v16M15 9h2a2 2 0 012 2v10M9 7h2M9 11h2M9 15h2" />
        }
        @case ('cube') {
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
          <path d="M3.27 6.96L12 12l8.73-5.04M12 22.08V12" />
        }
        @case ('pen-tool') {
          <path d="M12 19l7-7 3 3-7 7-3-3z" />
          <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
          <path d="M2 2l7.586 7.586" />
          <circle cx="11" cy="11" r="2" />
        }
        @case ('sparkles') {
          <path d="M12 3l1.8 4.6L18.5 9.5l-4.7 1.9L12 16l-1.8-4.6L5.5 9.5l4.7-1.9L12 3z" />
          <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15zM5 2l.6 1.5L7 4l-1.4.5L5 6l-.6-1.5L3 4l1.4-.5L5 2z" />
        }
        @case ('megaphone') {
          <path d="M3 11l18-7-4 14-6-3-4 3-2-4-2-3z" />
          <path d="M8 14l1.5 5" />
        }
        @case ('arrow-right') {
          <path d="M5 12h14M13 6l6 6-6 6" />
        }
        @case ('arrow-left') {
          <path d="M19 12H5M11 18l-6-6 6-6" />
        }
        @case ('calendar') {
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <path d="M16 2v4M8 2v4M3 10h18" />
        }
        @case ('alert-triangle') {
          <path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h16.9a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
          <path d="M12 9v4M12 17h.01" />
        }
        @case ('trending-up') {
          <path d="M23 6l-9.5 9.5-5-5L1 18" />
          <path d="M17 6h6v6" />
        }
        @case ('send') {
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        }
        @case ('menu') {
          <path d="M4 6h16M4 12h16M4 18h16" />
        }
        @case ('x') {
          <path d="M18 6L6 18M6 6l12 12" />
        }
        @case ('plus') {
          <path d="M12 5v14M5 12h14" />
        }
        @case ('minus') {
          <path d="M5 12h14" />
        }
        @case ('download') {
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
        }
        @case ('trash') {
          <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6M10 11v6M14 11v6" />
        }
        @case ('undo') {
          <path d="M3 7v6h6" />
          <path d="M21 17a9 9 0 00-9-9 9 9 0 00-6.4 2.6L3 13" />
        }
        @case ('redo') {
          <path d="M21 7v6h-6" />
          <path d="M3 17a9 9 0 019-9 9 9 0 016.4 2.6L21 13" />
        }
        @case ('save') {
          <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
          <path d="M17 21v-8H7v8M7 3v5h8" />
        }
        @case ('grid') {
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        }
        @case ('ruler') {
          <path d="M3 17l14-14 4 4L7 21l-4-4z" />
          <path d="M7 13l2 2M10 10l2 2M13 7l2 2" />
        }
        @case ('mouse-pointer') {
          <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
          <path d="M13 13l6 6" />
        }
        @case ('pencil') {
          <path d="M17 3a2.85 2.85 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
        }
        @case ('line') {
          <path d="M5 19L19 5" />
          <circle cx="5" cy="19" r="1.5" />
          <circle cx="19" cy="5" r="1.5" />
        }
        @case ('square') {
          <rect x="4" y="4" width="16" height="16" rx="2" />
        }
        @case ('eraser') {
          <path d="M20 20H9l-5-5a2 2 0 010-2.8l8.2-8.2a2 2 0 012.8 0l4 4a2 2 0 010 2.8L11 19" />
          <path d="M6.5 11.5L15 20" />
        }
        @case ('hand') {
          <path d="M18 11V6a2 2 0 00-4 0v5M14 10V4a2 2 0 00-4 0v6M10 10V6a2 2 0 00-4 0v8" />
          <path d="M18 8a2 2 0 014 0v6a8 8 0 01-8 8h-2a8 8 0 01-8-8v-1a2 2 0 014 0" />
        }
        @case ('rotate') {
          <path d="M23 4v6h-6M1 20v-6h6" />
          <path d="M3.5 9a9 9 0 0114.9-3.3L23 10M1 14l4.6 4.3A9 9 0 0020.5 15" />
        }
        @case ('compass') {
          <circle cx="12" cy="12" r="10" />
          <path d="M16.2 7.8l-2.1 6.3-6.3 2.1 2.1-6.3 6.3-2.1z" />
        }
        @case ('layers') {
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
        }
        @case ('search') {
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        }
        @case ('command') {
          <path d="M18 3a3 3 0 00-3 3v12a3 3 0 003 3 3 3 0 003-3 3 3 0 00-3-3H6a3 3 0 00-3 3 3 3 0 003 3 3 3 0 003-3V6a3 3 0 00-3-3 3 3 0 00-3 3 3 3 0 003 3h12a3 3 0 003-3 3 3 0 00-3-3z" />
        }
        @case ('activity') {
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        }
        @default {
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24" />
        }
      }
    </svg>
  `,
})
export class IconComponent {
  @Input() name: string = 'default';
  @Input() size: number = 18;
}
