import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { IconComponent } from '../../shared/icon.component';

export interface SitePlanZone {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
  progress: number;
  status: string;
  color: string;
  meta?: Record<string, number>;
}

export interface SitePlanMarker {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
}

export interface SitePlanLegendItem {
  kind: string;
  label: string;
  color: string;
}

export interface SitePlanStats {
  open_tasks: number;
  overdue_tasks: number;
  open_rfis: number;
  percent_complete: number;
  safety_incidents_90d: number;
}

export interface SitePlanData {
  project_id: string;
  project_name: string;
  project_code?: string;
  site_width: number;
  site_height: number;
  grid: number;
  north_angle: number;
  updated_at: string;
  health_score: number;
  health_status: string;
  boundary: { x: number; y: number; width: number; height: number };
  zones: SitePlanZone[];
  markers: SitePlanMarker[];
  legend: SitePlanLegendItem[];
  stats: SitePlanStats;
}

interface TooltipState {
  x: number;
  y: number;
}

@Component({
  selector: 'sf-site-plan',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './site-plan.component.html',
  styleUrl: './site-plan.component.css',
})
export class SitePlanComponent {
  private readonly svgRef = viewChild<ElementRef<SVGSVGElement>>('svg');
  private readonly canvasRef = viewChild<ElementRef<HTMLDivElement>>('canvas');

  readonly plan = input<SitePlanData | null>(null);
  readonly zoneSelected = output<SitePlanZone>();

  readonly zoom = signal(1);
  readonly pan = signal({ x: 0, y: 0 });
  readonly selectedId = signal<string | null>(null);
  readonly hoveredId = signal<string | null>(null);
  readonly tooltip = signal<TooltipState | null>(null);
  readonly layers = signal<Record<string, boolean>>({
    building: true,
    parking: true,
    laydown: true,
    equipment: true,
    access: true,
    utility: true,
    safety: true,
  });

  private panning = false;
  private panOrigin = { x: 0, y: 0, clientX: 0, clientY: 0 };

  readonly visibleZones = computed(() => {
    const plan = this.plan();
    const layers = this.layers();
    return plan ? plan.zones.filter((zone) => layers[zone.kind] !== false) : [];
  });

  readonly visibleMarkers = computed(() => {
    const plan = this.plan();
    const layers = this.layers();
    return plan ? plan.markers.filter((marker) => layers[marker.kind] !== false) : [];
  });

  readonly selectedZone = computed(
    () => this.visibleZones().find((zone) => zone.id === this.selectedId()) ?? null,
  );

  readonly hoveredZone = computed(
    () => this.visibleZones().find((zone) => zone.id === this.hoveredId()) ?? null,
  );

  readonly zoomLabel = computed(() => `${Math.round(this.zoom() * 100)}%`);

  readonly transform = computed(
    () => `translate(${this.pan().x} ${this.pan().y}) scale(${this.zoom()})`,
  );

  viewBox(): string {
    const plan = this.plan();
    return plan ? `0 0 ${plan.site_width} ${plan.site_height}` : '0 0 100 64';
  }

  healthLabel(status: string): string {
    const labels: Record<string, string> = {
      healthy: 'Healthy',
      at_risk: 'At risk',
      critical: 'Critical',
    };
    return labels[status] ?? status;
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      complete: 'Complete',
      active: 'In progress',
      planned: 'Planned',
    };
    return labels[status] ?? status;
  }

  isLayerOn(kind: string): boolean {
    return this.layers()[kind] !== false;
  }

  toggleLayer(kind: string): void {
    this.layers.update((layers) => ({ ...layers, [kind]: layers[kind] === false }));
  }

  markerColor(kind: string): string {
    return (
      this.plan()?.legend.find((item) => item.kind === kind)?.color ??
      (kind === 'safety' ? '#ef4444' : '#64748b')
    );
  }

  markerGlyph(marker: SitePlanMarker): string {
    const glyphs: Record<string, string> = {
      access: 'G',
      equipment: 'C',
      safety: '+',
      laydown: 'R',
    };
    return glyphs[marker.kind] ?? '•';
  }

  progressWidth(zone: SitePlanZone): number {
    return Math.max(0, (zone.width - 3) * (Math.min(100, zone.progress) / 100));
  }

  updatedLabel(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? 'just now'
      : date.toLocaleString(undefined, {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        });
  }

  selectZone(zone: SitePlanZone): void {
    this.selectedId.set(zone.id);
    this.zoneSelected.emit(zone);
  }

  clearSelection(): void {
    this.selectedId.set(null);
  }

  onZoneEnter(zone: SitePlanZone, event: MouseEvent): void {
    this.hoveredId.set(zone.id);
    this.updateTooltip(event);
  }

  onZoneLeave(): void {
    this.hoveredId.set(null);
    this.tooltip.set(null);
  }

  onPointerMove(event: MouseEvent): void {
    if (this.panning) {
      const rect = this.svgRef()?.nativeElement.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const unitsPerPixel = (this.plan()?.site_width ?? 100) / rect.width;
      const dx = (event.clientX - this.panOrigin.clientX) * unitsPerPixel;
      const dy = (event.clientY - this.panOrigin.clientY) * unitsPerPixel;
      this.pan.set({
        x: this.panOrigin.x + dx,
        y: this.panOrigin.y + dy,
      });
    }
    if (this.hoveredId()) {
      this.updateTooltip(event);
    }
  }

  onWheel(event: WheelEvent): void {
    const plan = this.plan();
    if (!plan) {
      return;
    }
    event.preventDefault();
    const rect = this.svgRef()?.nativeElement.getBoundingClientRect();
    if (!rect) {
      return;
    }
    const pointerX = ((event.clientX - rect.left) / rect.width) * plan.site_width;
    const pointerY = ((event.clientY - rect.top) / rect.height) * plan.site_height;
    const oldZoom = this.zoom();
    const nextZoom = Math.min(3, Math.max(0.6, oldZoom + (event.deltaY > 0 ? -0.12 : 0.12)));
    const pan = this.pan();
    const contentX = (pointerX - pan.x) / oldZoom;
    const contentY = (pointerY - pan.y) / oldZoom;
    this.zoom.set(nextZoom);
    this.pan.set({
      x: pointerX - contentX * nextZoom,
      y: pointerY - contentY * nextZoom,
    });
  }

  startPan(event: MouseEvent): void {
    if (event.button !== 0) {
      return;
    }
    this.panning = true;
    this.panOrigin = {
      x: this.pan().x,
      y: this.pan().y,
      clientX: event.clientX,
      clientY: event.clientY,
    };
  }

  stopPan(): void {
    this.panning = false;
  }

  zoomIn(): void {
    this.zoom.update((zoom) => Math.min(3, zoom + 0.15));
  }

  zoomOut(): void {
    this.zoom.update((zoom) => Math.max(0.6, zoom - 0.15));
  }

  fit(): void {
    this.zoom.set(1);
    this.pan.set({ x: 0, y: 0 });
  }

  private updateTooltip(event: MouseEvent): void {
    const rect = this.canvasRef()?.nativeElement.getBoundingClientRect();
    if (!rect) {
      return;
    }
    this.tooltip.set({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  }
}
