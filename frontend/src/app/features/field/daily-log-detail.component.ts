import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';

interface LabourEntry {
  id: string;
  trade: string;
  company?: string;
  headcount: number;
  hours: number;
  overtime_hours?: number;
  notes?: string;
}

interface EquipmentEntry {
  id: string;
  equipment_name: string;
  equipment_code?: string;
  hours: number;
  idle_hours?: number;
  owner?: string;
  notes?: string;
}

interface DailyLog {
  id: string;
  project: string;
  log_date: string;
  status: string;
  weather_summary?: string;
  work_activities?: string;
  delays?: string;
  safety_notes?: string;
  visitors?: string;
  labour_entries?: LabourEntry[];
  equipment_entries?: EquipmentEntry[];
  created_by?: { first_name: string; last_name: string; email: string };
  approved_by?: { first_name: string; last_name: string; email: string };
  approved_at?: string;
}

@Component({
  selector: 'sf-daily-log-detail',
  imports: [FormsModule, DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './daily-log-detail.component.html',
  styleUrl: './daily-log-detail.component.css',
})
export class DailyLogDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  readonly log = signal<DailyLog | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly actionLoading = signal(false);
  readonly actionError = signal('');

  readonly labourTrade = signal('');
  readonly labourCompany = signal('');
  readonly labourHeadcount = signal(0);
  readonly labourHours = signal(0);
  readonly labourOt = signal(0);

  readonly equipName = signal('');
  readonly equipCode = signal('');
  readonly equipHours = signal(0);
  readonly equipIdle = signal(0);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.load(id);
    } else {
      this.loading.set(false);
      this.error.set('Daily log not found');
    }
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.api.get<DailyLog>(`daily-logs/${id}/`).subscribe({
      next: (log) => {
        this.log.set(log);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.api.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  submit(): void {
    const log = this.log();
    if (!log) return;
    this.actionLoading.set(true);
    this.api.post<DailyLog>(`daily-logs/${log.id}/submit/`, {}).subscribe({
      next: (updated) => {
        this.log.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  approve(): void {
    const log = this.log();
    if (!log) return;
    this.actionLoading.set(true);
    this.api.post<DailyLog>(`daily-logs/${log.id}/approve/`, {}).subscribe({
      next: (updated) => {
        this.log.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  reject(): void {
    const log = this.log();
    if (!log) return;
    this.actionLoading.set(true);
    this.api.post<DailyLog>(`daily-logs/${log.id}/reject/`, {}).subscribe({
      next: (updated) => {
        this.log.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionError.set(this.api.errorMessage(err));
        this.actionLoading.set(false);
      },
    });
  }

  addLabour(): void {
    const log = this.log();
    if (!log || !this.labourTrade().trim()) {
      this.actionError.set('Enter a trade.');
      return;
    }
    this.actionLoading.set(true);
    this.api
      .post<LabourEntry>('labour-entries/', {
        daily_log: log.id,
        trade: this.labourTrade().trim(),
        company: this.labourCompany().trim() || undefined,
        headcount: Number(this.labourHeadcount()) || 0,
        hours: Number(this.labourHours()) || 0,
        overtime_hours: Number(this.labourOt()) || 0,
      })
      .subscribe({
        next: (entry) => {
          this.log.update((current) =>
            current ? { ...current, labour_entries: [...(current.labour_entries ?? []), entry] } : current,
          );
          this.labourTrade.set('');
          this.labourCompany.set('');
          this.labourHeadcount.set(0);
          this.labourHours.set(0);
          this.labourOt.set(0);
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionError.set(this.api.errorMessage(err));
          this.actionLoading.set(false);
        },
      });
  }

  addEquipment(): void {
    const log = this.log();
    if (!log || !this.equipName().trim()) {
      this.actionError.set('Enter equipment name.');
      return;
    }
    this.actionLoading.set(true);
    this.api
      .post<EquipmentEntry>('equipment-entries/', {
        daily_log: log.id,
        equipment_name: this.equipName().trim(),
        equipment_code: this.equipCode().trim() || undefined,
        hours: Number(this.equipHours()) || 0,
        idle_hours: Number(this.equipIdle()) || 0,
      })
      .subscribe({
        next: (entry) => {
          this.log.update((current) =>
            current ? { ...current, equipment_entries: [...(current.equipment_entries ?? []), entry] } : current,
          );
          this.equipName.set('');
          this.equipCode.set('');
          this.equipHours.set(0);
          this.equipIdle.set(0);
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionError.set(this.api.errorMessage(err));
          this.actionLoading.set(false);
        },
      });
  }

  displayUser(user?: { first_name: string; last_name: string; email: string }): string {
    if (!user) return '—';
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
    return name || user.email;
  }
}
