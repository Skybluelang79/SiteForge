import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';

@Component({
  selector: 'sf-auth-canvas',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="canvas-shell">
      <canvas #canvas aria-hidden="true"></canvas>
      <div class="canvas-caption" aria-hidden="true">
        <span>SF / BLUEPRINT 04</span>
        <span>GRID A-1 · SCALE 1:100</span>
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        height: 100%;
      }

      .canvas-shell {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        border-radius: inherit;
      }

      canvas {
        display: block;
        width: 100%;
        height: 100%;
      }

      .canvas-caption {
        position: absolute;
        left: 16px;
        right: 16px;
        bottom: 12px;
        display: flex;
        justify-content: space-between;
        gap: 12px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: rgba(148, 163, 184, 0.7);
        pointer-events: none;
      }
    `,
  ],
})
export class AuthCanvasComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private canvasRef!: ElementRef<HTMLCanvasElement>;

  private readonly zone = inject(NgZone);
  private observer?: ResizeObserver;
  private resizeHandler?: () => void;

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      const canvas = this.canvasRef.nativeElement;
      if (typeof ResizeObserver !== 'undefined') {
        this.observer = new ResizeObserver(() => this.draw(canvas));
        this.observer.observe(canvas.parentElement ?? canvas);
      } else {
        this.resizeHandler = () => this.draw(canvas);
        window.addEventListener('resize', this.resizeHandler);
      }
      this.draw(canvas);
    });
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler);
    }
  }

  private draw(canvas: HTMLCanvasElement): void {
    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }
    const width = Math.max(280, canvas.clientWidth || canvas.parentElement?.clientWidth || 640);
    const height = Math.max(140, canvas.clientHeight || canvas.parentElement?.clientHeight || 200);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const background = context.createLinearGradient(0, 0, width, height);
    background.addColorStop(0, '#0b1220');
    background.addColorStop(0.55, '#101c31');
    background.addColorStop(1, '#142746');
    context.fillStyle = background;
    context.fillRect(0, 0, width, height);

    const glow = context.createRadialGradient(width * 0.78, height * 0.2, 0, width * 0.78, height * 0.2, width * 0.62);
    glow.addColorStop(0, 'rgba(245, 158, 11, 0.2)');
    glow.addColorStop(0.55, 'rgba(56, 189, 248, 0.06)');
    glow.addColorStop(1, 'rgba(15, 23, 42, 0)');
    context.fillStyle = glow;
    context.fillRect(0, 0, width, height);

    for (let x = 0; x <= width; x += 24) {
      context.strokeStyle = x % 96 === 0 ? 'rgba(148, 163, 184, 0.18)' : 'rgba(148, 163, 184, 0.07)';
      context.beginPath();
      context.moveTo(x + 0.5, 0);
      context.lineTo(x + 0.5, height);
      context.stroke();
    }
    for (let y = 0; y <= height; y += 24) {
      context.strokeStyle = y % 96 === 0 ? 'rgba(148, 163, 184, 0.18)' : 'rgba(148, 163, 184, 0.07)';
      context.beginPath();
      context.moveTo(0, y + 0.5);
      context.lineTo(width, y + 0.5);
      context.stroke();
    }

    const centerX = width * 0.5;
    const centerY = height * 0.5;
    const size = Math.min(width * 0.2, height * 0.62);
    const top = { x: centerX, y: centerY - size * 0.6 };
    const right = { x: centerX + size * 1.45, y: centerY - size * 0.05 };
    const bottom = { x: centerX + size * 0.58, y: centerY + size * 0.72 };
    const left = { x: centerX - size * 0.88, y: centerY + size * 0.18 };
    const points = [top, right, bottom, left];

    context.save();
    context.strokeStyle = 'rgba(56, 189, 248, 0.72)';
    context.lineWidth = 1.4;
    context.beginPath();
    context.moveTo(top.x, top.y);
    points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
    context.closePath();
    context.stroke();

    context.strokeStyle = 'rgba(148, 163, 184, 0.32)';
    context.lineWidth = 1;
    for (let step = 1; step < 4; step += 1) {
      const t = step / 4;
      context.beginPath();
      context.moveTo(
        top.x + (left.x - top.x) * t,
        top.y + (left.y - top.y) * t,
      );
      context.lineTo(
        right.x + (bottom.x - right.x) * t,
        right.y + (bottom.y - right.y) * t,
      );
      context.stroke();
      context.beginPath();
      context.moveTo(
        top.x + (right.x - top.x) * t,
        top.y + (right.y - top.y) * t,
      );
      context.lineTo(
        left.x + (bottom.x - left.x) * t,
        left.y + (bottom.y - left.y) * t,
      );
      context.stroke();
    }

    context.fillStyle = '#fbbf24';
    points.forEach((point) => {
      context.beginPath();
      context.arc(point.x, point.y, 2.4, 0, Math.PI * 2);
      context.fill();
    });
    context.restore();

    context.strokeStyle = 'rgba(245, 158, 11, 0.55)';
    context.lineWidth = 1;
    context.setLineDash([4, 4]);
    context.beginPath();
    context.moveTo(20, centerY);
    context.lineTo(width - 20, centerY);
    context.moveTo(centerX, 18);
    context.lineTo(centerX, height - 30);
    context.stroke();
    context.setLineDash([]);

    context.strokeStyle = 'rgba(148, 163, 184, 0.5)';
    const bracket = 12;
    const corners = [
      { x: 16, y: 16, dx: 1, dy: 1 },
      { x: width - 16, y: 16, dx: -1, dy: 1 },
      { x: 16, y: height - 16, dx: 1, dy: -1 },
      { x: width - 16, y: height - 16, dx: -1, dy: -1 },
    ];
    corners.forEach((corner) => {
      context.beginPath();
      context.moveTo(corner.x, corner.y + corner.dy * bracket);
      context.lineTo(corner.x, corner.y);
      context.lineTo(corner.x + corner.dx * bracket, corner.y);
      context.stroke();
    });

    context.font = '700 9px ui-monospace, SFMono-Regular, Consolas, monospace';
    context.fillStyle = 'rgba(148, 163, 184, 0.65)';
    context.fillText('A', 18, centerY - 6);
    context.fillText('B', centerX + 8, 26);
    context.fillText('EL +12.400', width - 104, centerY - 6);
  }
}
