import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'sf-sparkline',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg [attr.viewBox]="'0 0 100 ' + height" preserveAspectRatio="none" aria-hidden="true">
      <polygon [attr.points]="area()" [attr.fill]="color" fill-opacity="0.12" />
      <polyline
        [attr.points]="line()"
        fill="none"
        [attr.stroke]="color"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        vector-effect="non-scaling-stroke"
      />
      @if (last(); as point) {
        <circle [attr.cx]="point.x" [attr.cy]="point.y" r="2.2" [attr.fill]="color" />
      }
    </svg>
  `,
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        height: 100%;
      }
      svg {
        width: 100%;
        height: 100%;
        overflow: visible;
      }
    `,
  ],
})
export class SparklineComponent {
  @Input() values: number[] = [3, 5, 4, 7, 6, 9, 8, 12, 11, 14];
  @Input() color = '#f59e0b';
  @Input() height = 36;
  @Input() padding = 3;

  line(): string {
    return this.points()
      .map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)
      .join(' ');
  }

  area(): string {
    const points = this.points();
    if (!points.length) {
      return '';
    }
    const first = points[0];
    const final = points[points.length - 1];
    return `${first.x},${this.height} ${this.line()} ${final.x},${this.height}`;
  }

  last(): { x: number; y: number } | null {
    const points = this.points();
    return points.length ? points[points.length - 1] : null;
  }

  private points(): { x: number; y: number }[] {
    const values = this.values.length ? this.values : [0];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const usable = this.height - this.padding * 2;
    return values.map((value, index) => ({
      x: values.length === 1 ? 50 : (index / (values.length - 1)) * 100,
      y: this.padding + usable - ((value - min) / range) * usable,
    }));
  }
}
