import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { DesignService, CanvasBoard } from '../../core/design.service';
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

interface CanvasState {
  version: number;
  zoom: number;
  showGrid: boolean;
  objects: CanvasObject[];
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
  private readonly design = inject(DesignService);
  private readonly api = inject(ApiService);

  readonly canvasEl = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  readonly objects = signal<CanvasObject[]>([]);
  readonly selectedId = signal<string | null>(null);
  readonly zoom = signal(1);
  readonly showGrid = signal(true);
  readonly tool = signal<'select' | 'rect' | 'circle' | 'triangle' | 'line' | 'text'>('select');

  readonly boards = signal<CanvasBoard[]>([]);
  readonly selectedBoardId = signal<string | null>(null);
  readonly boardName = signal('Main Canvas');
  readonly loadingBoards = signal(false);
  readonly saving = signal(false);
  readonly status = signal('');
  readonly error = signal('');

  private ctx!: CanvasRenderingContext2D;
  private isDragging = false;
  private dragStart = { x: 0, y: 0 };
  private selected: CanvasObject | null = null;
  private ctxReady = false;

  constructor() {
    effect(() => {
      const projectId = this.auth.activeProjectId();
      untracked(() => this.onProjectChange(projectId));
    });
  }

  ngAfterViewInit(): void {
    const canvas = this.canvasEl().nativeElement;
    const parent = canvas.parentElement!;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight - 10;
    this.ctx = canvas.getContext('2d')!;
    this.ctxReady = true;
    this.draw();
    window.addEventListener('resize', () => this.resize());
  }

  private onProjectChange(projectId: string | null): void {
    this.boards.set([]);
    this.selectedBoardId.set(null);
    this.status.set('');
    this.error.set('');
    this.boardName.set('Main Canvas');
    this.objects.set([]);
    this.selectedId.set(null);
    this.selected = null;
    this.zoom.set(1);
    this.showGrid.set(true);
    if (projectId) {
      this.loadBoards(projectId);
    } else {
      this.draw();
    }
  }

  loadBoards(projectId?: string): void {
    const id = projectId ?? this.auth.activeProjectId();
    if (!id) return;
    this.loadingBoards.set(true);
    this.error.set('');
    this.design.listBoards(id).subscribe({
      next: (boards) => {
        this.boards.set(boards);
        if (boards.length > 0) {
          this.applyBoard(boards[0]);
          this.status.set('Canvas loaded.');
        } else {
          this.status.set('No saved canvases for this project yet.');
          this.draw();
        }
        this.loadingBoards.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loadingBoards.set(false);
      },
    });
  }

  loadSelected(): void {
    const board = this.boards().find((b) => b.id === this.selectedBoardId());
    if (!board) {
      this.error.set('Select a canvas to load.');
      return;
    }
    this.error.set('');
    this.applyBoard(board);
    this.status.set(`Loaded "${board.name}".`);
  }

  onBoardSelectionChange(id: string): void {
    this.selectedBoardId.set(id || null);
  }

  onBoardNameInput(value: string): void {
    this.boardName.set(value);
  }

  private applyBoard(board: CanvasBoard): void {
    this.selectedBoardId.set(board.id);
    this.boardName.set(board.name);
    const state = (board.state ?? {}) as Partial<CanvasState>;
    this.objects.set(Array.isArray(state.objects) ? (state.objects as CanvasObject[]) : []);
    this.zoom.set(typeof state.zoom === 'number' ? state.zoom : 1);
    this.showGrid.set(typeof state.showGrid === 'boolean' ? state.showGrid : true);
    this.selectedId.set(null);
    this.selected = null;
    this.draw();
  }

  saveBoard(): void {
    const projectId = this.auth.activeProjectId();
    if (!projectId) {
      this.error.set('Select an active project before saving.');
      return;
    }
    const name = this.boardName().trim() || 'Main Canvas';
    const payload = { name, state: this.serializeState() };
    this.saving.set(true);
    this.error.set('');
    this.status.set('');

    const currentId = this.selectedBoardId();
    const request = currentId
      ? this.design.updateBoard(currentId, payload)
      : this.design.createBoard({ project: projectId, ...payload });

    request.subscribe({
      next: (board) => {
        const existing = this.boards();
        const idx = existing.findIndex((b) => b.id === board.id);
        const updated = idx >= 0 ? existing.map((b) => (b.id === board.id ? board : b)) : [board, ...existing];
        this.boards.set(updated);
        this.selectedBoardId.set(board.id);
        this.boardName.set(board.name);
        this.status.set(currentId ? 'Canvas saved.' : 'Canvas created.');
        this.saving.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.saving.set(false);
      },
    });
  }

  saveAsNew(): void {
    this.selectedBoardId.set(null);
    this.saveBoard();
  }

  private serializeState(): CanvasState {
    return {
      version: 1,
      zoom: this.zoom(),
      showGrid: this.showGrid(),
      objects: this.objects(),
    };
  }

  resize(): void {
    if (!this.ctxReady) return;
    const canvas = this.canvasEl().nativeElement;
    const parent = canvas.parentElement!;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight - 10;
    this.draw();
  }

  selectTool(t: 'select' | 'rect' | 'circle' | 'triangle' | 'line' | 'text'): void {
    this.tool.set(t);
  }

  loadAuthMockup(): void {
    const make = (
      object: Partial<CanvasObject> & Pick<CanvasObject, 'type' | 'x' | 'y' | 'width' | 'height'>,
    ): CanvasObject => ({
      id: crypto.randomUUID(),
      rotation: 0,
      fill: '#ffffff',
      stroke: '#cbd5e1',
      strokeWidth: 1,
      ...object,
    });

    this.objects.set([
      make({ type: 'rect', x: 40, y: 40, width: 760, height: 500, fill: '#f8fafc', stroke: '#cbd5e1' }),
      make({ type: 'text', x: 64, y: 64, width: 420, height: 32, fill: '#0f172a', stroke: 'transparent', strokeWidth: 0, text: 'SiteForge — secure access flow', fontSize: 22 }),
      make({ type: 'text', x: 64, y: 94, width: 500, height: 24, fill: '#64748b', stroke: 'transparent', strokeWidth: 0, text: 'Credentials  →  Cloudflare verification  →  Project workspace', fontSize: 13 }),
      make({ type: 'rect', x: 64, y: 140, width: 210, height: 330, fill: '#ffffff', stroke: '#94a3b8' }),
      make({ type: 'text', x: 80, y: 160, width: 180, height: 24, fill: '#0f172a', stroke: 'transparent', strokeWidth: 0, text: '1 · Credentials', fontSize: 16 }),
      make({ type: 'text', x: 80, y: 190, width: 180, height: 20, fill: '#64748b', stroke: 'transparent', strokeWidth: 0, text: 'Work email', fontSize: 12 }),
      make({ type: 'rect', x: 80, y: 212, width: 178, height: 30, fill: '#f1f5f9', stroke: '#cbd5e1' }),
      make({ type: 'text', x: 88, y: 234, width: 160, height: 18, fill: '#94a3b8', stroke: 'transparent', strokeWidth: 0, text: 'you@company.com', fontSize: 12 }),
      make({ type: 'text', x: 80, y: 258, width: 180, height: 20, fill: '#64748b', stroke: 'transparent', strokeWidth: 0, text: 'Password', fontSize: 12 }),
      make({ type: 'rect', x: 80, y: 280, width: 178, height: 30, fill: '#f1f5f9', stroke: '#cbd5e1' }),
      make({ type: 'text', x: 88, y: 302, width: 160, height: 18, fill: '#94a3b8', stroke: 'transparent', strokeWidth: 0, text: '••••••••••', fontSize: 12 }),
      make({ type: 'rect', x: 80, y: 336, width: 178, height: 26, fill: '#eff6ff', stroke: '#bfdbfe' }),
      make({ type: 'text', x: 88, y: 354, width: 160, height: 18, fill: '#2563eb', stroke: 'transparent', strokeWidth: 0, text: 'Turnstile verification', fontSize: 11 }),
      make({ type: 'rect', x: 80, y: 382, width: 178, height: 36, fill: '#f59e0b', stroke: '#d97706' }),
      make({ type: 'text', x: 128, y: 406, width: 100, height: 20, fill: '#ffffff', stroke: 'transparent', strokeWidth: 0, text: 'Continue', fontSize: 14 }),
      make({ type: 'line', x: 282, y: 300, width: 60, height: 0, stroke: '#94a3b8', strokeWidth: 2 }),
      make({ type: 'triangle', x: 334, y: 294, width: 14, height: 12, fill: '#94a3b8', stroke: '#94a3b8' }),
      make({ type: 'rect', x: 364, y: 140, width: 210, height: 330, fill: '#ffffff', stroke: '#94a3b8' }),
      make({ type: 'text', x: 380, y: 160, width: 180, height: 24, fill: '#0f172a', stroke: 'transparent', strokeWidth: 0, text: '2 · Verify', fontSize: 16 }),
      make({ type: 'circle', x: 430, y: 206, width: 78, height: 78, fill: '#eff6ff', stroke: '#3b82f6', strokeWidth: 2 }),
      make({ type: 'text', x: 458, y: 248, width: 30, height: 28, fill: '#2563eb', stroke: 'transparent', strokeWidth: 0, text: '✓', fontSize: 24 }),
      make({ type: 'text', x: 386, y: 310, width: 166, height: 20, fill: '#334155', stroke: 'transparent', strokeWidth: 0, text: 'Turnstile challenge', fontSize: 13 }),
      make({ type: 'text', x: 386, y: 338, width: 166, height: 20, fill: '#334155', stroke: 'transparent', strokeWidth: 0, text: 'Cloudflare Access JWT', fontSize: 13 }),
      make({ type: 'text', x: 386, y: 366, width: 166, height: 20, fill: '#334155', stroke: 'transparent', strokeWidth: 0, text: 'Device + session trust', fontSize: 13 }),
      make({ type: 'rect', x: 386, y: 406, width: 166, height: 32, fill: '#ecfdf5', stroke: '#a7f3d0' }),
      make({ type: 'text', x: 406, y: 428, width: 130, height: 20, fill: '#047857', stroke: 'transparent', strokeWidth: 0, text: 'Verified', fontSize: 13 }),
      make({ type: 'line', x: 582, y: 300, width: 60, height: 0, stroke: '#94a3b8', strokeWidth: 2 }),
      make({ type: 'triangle', x: 634, y: 294, width: 14, height: 12, fill: '#94a3b8', stroke: '#94a3b8' }),
      make({ type: 'rect', x: 664, y: 140, width: 112, height: 330, fill: '#ffffff', stroke: '#94a3b8' }),
      make({ type: 'text', x: 678, y: 160, width: 90, height: 24, fill: '#0f172a', stroke: 'transparent', strokeWidth: 0, text: '3 · Workspace', fontSize: 12 }),
      make({ type: 'rect', x: 678, y: 196, width: 20, height: 250, fill: '#0f172a', stroke: '#0f172a' }),
      make({ type: 'rect', x: 708, y: 196, width: 54, height: 12, fill: '#cbd5e1', stroke: '#cbd5e1' }),
      make({ type: 'rect', x: 708, y: 220, width: 54, height: 58, fill: '#f59e0b33', stroke: '#f59e0b' }),
      make({ type: 'rect', x: 708, y: 290, width: 54, height: 58, fill: '#3b82f633', stroke: '#3b82f6' }),
      make({ type: 'rect', x: 708, y: 360, width: 54, height: 58, fill: '#22c55e33', stroke: '#22c55e' }),
      make({ type: 'text', x: 64, y: 500, width: 700, height: 20, fill: '#64748b', stroke: 'transparent', strokeWidth: 0, text: 'Save as a new canvas to keep this mockup with the active project.', fontSize: 12 }),
    ]);
    this.selectedBoardId.set(null);
    this.boardName.set('Auth flow mockup');
    this.selectedId.set(null);
    this.selected = null;
    this.error.set('');
    this.status.set('Auth-flow mockup loaded.');
    this.draw();
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
      objs.map((o) =>
        o.id === this.selected!.id ? { ...o, x: x - this.dragStart.x, y: y - this.dragStart.y } : o,
      ),
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
    if (!this.ctxReady) return;
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
        ctx.roundRect
          ? ctx.roundRect(obj.x, obj.y, obj.width, obj.height, 4)
          : ctx.rect(obj.x, obj.y, obj.width, obj.height);
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
      objs.map((o) =>
        o.id === this.selectedId()
          ? {
              ...o,
              [prop]:
                typeof value === 'string' && prop !== 'text' && prop !== 'fill' && prop !== 'stroke'
                  ? Number(value)
                  : value,
            }
          : o,
      ),
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
