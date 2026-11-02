import { ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../shared/icon.component';

interface CanvasObject {
  id: string;
  type: 'rect' | 'circle' | 'triangle' | 'line' | 'text' | 'image';
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  fill: string;
  stroke: string;
  strokeWidth: number;
  text?: string;
  fontSize?: number;
  locked?: boolean;
}

@Component({
  selector: 'sf-design-canvas',
  imports: [FormsModule, RouterLink, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './design-canvas.component.css',
  templateUrl: './design-canvas.component.html',
})
export class DesignCanvasComponent {
  readonly auth = inject(AuthService);

  readonly canvasEl = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  readonly objects = signal<CanvasObject[]>([]);
  readonly selectedId = signal<string | null>(null);
  readonly zoom = signal(1);
  readonly showGrid = signal(true);
  readonly tool = signal<'select' | 'rect' | 'circle' | 'triangle' | 'line' | 'text'>('select');

  private ctx!: CanvasRenderingContext2D;
  private isDragging = false;
  private dragStart = { x: 0, y: 0 };
  private selected: CanvasObject | null = null;

  ngAfterViewInit(): void {
    const canvas = this.canvasEl().nativeElement;
    const parent = canvas.parentElement!;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight - 10;
    this.ctx = canvas.getContext('2d')!;
    this.draw();
    window.addEventListener('resize', () => this.resize());
  }

  resize(): void {
    const canvas = this.canvasEl().nativeElement;
    const parent = canvas.parentElement!;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight - 10;
    this.draw();
  }

  selectTool(t: 'select' | 'rect' | 'circle' | 'triangle' | 'line' | 'text'): void {
    this.tool.set(t);
  }

  addRect(): void {
    const obj: CanvasObject = {
      id: crypto.randomUUID(),
      type: 'rect',
      x: 120,
      y: 120,
      width: 160,
      height: 100,
      rotation: 0,
      fill: '#f59e0b33',
      stroke: '#f59e0b',
      strokeWidth: 2,
    };
    this.objects.update((o) => [...o, obj]);
    this.select(obj.id);
    this.draw();
  }

  addCircle(): void {
    const obj: CanvasObject = {
      id: crypto.randomUUID(),
      type: 'circle',
      x: 200,
      y: 200,
      width: 120,
      height: 120,
      rotation: 0,
      fill: '#3b82f633',
      stroke: '#3b82f6',
      strokeWidth: 2,
    };
    this.objects.update((o) => [...o, obj]);
    this.select(obj.id);
    this.draw();
  }

  addTriangle(): void {
    const obj: CanvasObject = {
      id: crypto.randomUUID(),
      type: 'triangle',
      x: 260,
      y: 160,
      width: 140,
      height: 120,
      rotation: 0,
      fill: '#22c55e33',
      stroke: '#22c55e',
      strokeWidth: 2,
    };
    this.objects.update((o) => [...o, obj]);
    this.select(obj.id);
    this.draw();
  }

  addText(): void {
    const obj: CanvasObject = {
      id: crypto.randomUUID(),
      type: 'text',
      x: 180,
      y: 240,
      width: 220,
      height: 40,
      rotation: 0,
      fill: '#0f172a',
      stroke: 'transparent',
      strokeWidth: 0,
      text: 'Double click to edit',
      fontSize: 18,
    };
    this.objects.update((o) => [...o, obj]);
    this.select(obj.id);
    this.draw();
  }

  select(id: string): void {
    this.selectedId.set(id);
    this.selected = this.objects().find((o) => o.id === id) ?? null;
    this.draw();
  }

  onMouseDown(e: MouseEvent): void {
    const canvas = this.canvasEl().nativeElement;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / this.zoom();
    const y = (e.clientY - rect.top) / this.zoom();

    const hit = [...this.objects()].reverse().find((obj) => this.hitTest(obj, x, y));
    if (hit) {
      this.select(hit.id);
      this.isDragging = true;
      this.dragStart = { x: x - hit.x, y: y - hit.y };
    } else {
      this.selectedId.set(null);
      this.selected = null;
      this.draw();
    }
  }

  onMouseMove(e: MouseEvent): void {
    if (!this.isDragging || !this.selected) return;
    const canvas = this.canvasEl().nativeElement;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / this.zoom();
    const y = (e.clientY - rect.top) / this.zoom();
    this.objects.update((objs) =>
      objs.map((o) => (o.id === this.selected!.id ? { ...o, x: x - this.dragStart.x, y: y - this.dragStart.y } : o)),
    );
    this.selected = this.objects().find((o) => o.id === this.selected!.id)!;
    this.draw();
  }

  onMouseUp(): void {
    this.isDragging = false;
  }

  hitTest(obj: CanvasObject, x: number, y: number): boolean {
    if (obj.type === 'circle') {
      const cx = obj.x + obj.width / 2;
      const cy = obj.y + obj.height / 2;
      const r = obj.width / 2;
      const dx = x - cx;
      const dy = y - cy;
      return dx * dx + dy * dy <= r * r;
    }
    if (obj.type === 'triangle') {
      return x >= obj.x && x <= obj.x + obj.width && y >= obj.y && y <= obj.y + obj.height;
    }
    return x >= obj.x && x <= obj.x + obj.width && y >= obj.y && y <= obj.y + obj.height;
  }

  deleteSelected(): void {
    if (!this.selectedId()) return;
    this.objects.update((o) => o.filter((obj) => obj.id !== this.selectedId()));
    this.selectedId.set(null);
    this.selected = null;
    this.draw();
  }

  bringForward(): void {
    const id = this.selectedId();
    if (!id) return;
    const arr = [...this.objects()];
    const idx = arr.findIndex((o) => o.id === id);
    if (idx >= 0 && idx < arr.length - 1) {
      [arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]];
      this.objects.set(arr);
      this.draw();
    }
  }

  sendBackward(): void {
    const id = this.selectedId();
    if (!id) return;
    const arr = [...this.objects()];
    const idx = arr.findIndex((o) => o.id === id);
    if (idx > 0) {
      [arr[idx], arr[idx - 1]] = [arr[idx - 1], arr[idx]];
      this.objects.set(arr);
      this.draw();
    }
  }

  toggleGrid(): void {
    this.showGrid.update((g) => !g);
    this.draw();
  }

  zoomIn(): void {
    this.zoom.update((z) => Math.min(2, z + 0.1));
    this.draw();
  }

  zoomOut(): void {
    this.zoom.update((z) => Math.max(0.5, z - 0.1));
    this.draw();
  }

  fitToScreen(): void {
    this.zoom.set(1);
    this.draw();
  }

  draw(): void {
    const canvas = this.canvasEl().nativeElement;
    const ctx = this.ctx;
    ctx.setTransform(this.zoom(), 0, 0, this.zoom(), 0, 0);
    ctx.clearRect(0, 0, canvas.width / this.zoom(), canvas.height / this.zoom());

    if (this.showGrid()) {
      ctx.save();
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width / this.zoom(); x += 20) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height / this.zoom());
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height / this.zoom(); y += 20) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width / this.zoom(), y);
        ctx.stroke();
      }
      ctx.restore();
    }

    for (const obj of this.objects()) {
      ctx.save();
      ctx.translate(obj.x + obj.width / 2, obj.y + obj.height / 2);
      ctx.rotate((obj.rotation * Math.PI) / 180);
      ctx.translate(-(obj.x + obj.width / 2), -(obj.y + obj.height / 2));

      ctx.fillStyle = obj.fill;
      ctx.strokeStyle = obj.stroke;
      ctx.lineWidth = obj.strokeWidth;

      if (obj.type === 'rect') {
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(obj.x, obj.y, obj.width, obj.height, 4) : ctx.rect(obj.x, obj.y, obj.width, obj.height);
        ctx.fill();
        ctx.stroke();
      } else if (obj.type === 'circle') {
        ctx.beginPath();
        ctx.arc(obj.x + obj.width / 2, obj.y + obj.height / 2, obj.width / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      } else if (obj.type === 'triangle') {
        ctx.beginPath();
        ctx.moveTo(obj.x + obj.width / 2, obj.y);
        ctx.lineTo(obj.x + obj.width, obj.y + obj.height);
        ctx.lineTo(obj.x, obj.y + obj.height);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else if (obj.type === 'line') {
        ctx.beginPath();
        ctx.moveTo(obj.x, obj.y);
        ctx.lineTo(obj.x + obj.width, obj.y);
        ctx.stroke();
      } else if (obj.type === 'text') {
        ctx.fillStyle = obj.fill;
        ctx.font = `${obj.fontSize ?? 18}px Inter, system-ui, sans-serif`;
        ctx.fillText(obj.text ?? '', obj.x, obj.y + (obj.fontSize ?? 18));
      }

      if (this.selectedId() === obj.id) {
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(obj.x - 4, obj.y - 4, obj.width + 8, obj.height + 8);
        ctx.setLineDash([]);
      }
      ctx.restore();
    }
  }

  updateSelected(prop: keyof CanvasObject, value: string | number): void {
    if (!this.selectedId()) return;
    this.objects.update((objs) =>
      objs.map((o) => (o.id === this.selectedId() ? { ...o, [prop]: typeof value === 'string' && prop !== 'text' && prop !== 'fill' && prop !== 'stroke' ? Number(value) : value } : o)),
    );
    this.selected = this.objects().find((o) => o.id === this.selectedId())!;
    this.draw();
  }

  exportPNG(): void {
    const canvas = this.canvasEl().nativeElement;
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `siteforge-design-${Date.now()}.png`;
    a.click();
  }

  clearAll(): void {
    this.objects.set([]);
    this.selectedId.set(null);
    this.selected = null;
    this.draw();
  }
}
