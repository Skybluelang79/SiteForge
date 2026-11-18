import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  signal,
} from '@angular/core';

import { IconComponent } from './icon.component';

export interface SitePlanProject {
  id: string;
  name: string;
  number?: string;
  status?: string;
  city?: string;
  region?: string;
  percent_complete?: number;
  risk_score?: number;
  risk_level?: 'healthy' | 'watch' | 'at_risk' | 'critical' | string;
  open_items?: number;
  overdue_items?: number;
  contract_value?: number;
  currency?: string;
  target_completion_date?: string | null;
}

interface PlanBlock {
  project: SitePlanProject;
  x: number;
  y: number;
  width: number;
  height: number;
  level: string;
  progress: number;
}

const COLUMNS = 3;
const BLOCK_WIDTH = 236;
const BLOCK_HEIGHT = 126;
const GAP_X = 26;
const GAP_Y = 30;
const ORIGIN_X = 64;
const ORIGIN_Y = 96;

@Component({
  selector: 'sf-site-plan',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './site-plan.component.html',
  styleUrl: './site-plan.component.css',
})
export class SitePlanComponent {
  @Input() projects: SitePlanProject[] = [];
  @Input() selectedId: string | null = null;
  @Output() projectSelected = new EventEmitter<SitePlanProject>();

  readonly localSelection = signal<string | null>(null);

  get selected(): SitePlanProject | null {
    const id = this.localSelection() ?? this.selectedId;
    return (
      this.projects.find((project) => project.id === id) ??
      this.projects[0] ??
      null
    );
  }

  get rows(): number {
    return Math.max(1, Math.ceil(this.projects.length / COLUMNS));
  }

  get viewHeight(): number {
    return ORIGIN_Y + this.rows * (BLOCK_HEIGHT + GAP_Y) + 54;
  }

  blocks(): PlanBlock[] {
    return this.projects.map((project, index) => {
      const column = index % COLUMNS;
      const row = Math.floor(index / COLUMNS);
      return {
        project,
        x: ORIGIN_X + column * (BLOCK_WIDTH + GAP_X),
        y: ORIGIN_Y + row * (BLOCK_HEIGHT + GAP_Y),
        width: BLOCK_WIDTH,
        height: BLOCK_HEIGHT,
        level: project.risk_level ?? 'healthy',
        progress: Math.max(0, Math.min(100, project.percent_complete ?? 0)),
      };
    });
  }

  select(project: SitePlanProject): void {
    this.localSelection.set(project.id);
    this.projectSelected.emit(project);
  }

  levelLabel(level: string): string {
    return level.replace('_', ' ');
  }

  shortName(value: string): string {
    return value.length > 24 ? `${value.slice(0, 23)}…` : value;
  }

  money(value: number | undefined): string {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(value ?? 0);
  }

  riskScore(project: SitePlanProject): number {
    return Math.max(0, Math.min(100, Math.round(project.risk_score ?? 100)));
  }
}
