import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';

interface Task {
  id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  assignee?: { id: string; first_name: string; last_name: string; email: string } | null;
  due_date?: string | null;
  progress_percent?: number;
  project: string;
}

const COLUMNS = [
  { key: 'not_started', label: 'Not started' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'review', label: 'Review' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'done', label: 'Done' },
];

@Component({
  selector: 'sf-task-board',
  imports: [FormsModule, DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './task-board.component.html',
  styleUrl: './task-board.component.css',
})
export class TaskBoardComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly columns = COLUMNS;
  readonly tasks = signal<Task[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly dragTask = signal<Task | null>(null);
  readonly showForm = signal(false);
  readonly formTitle = signal('');
  readonly formPriority = signal('medium');
  readonly formDue = signal('');
  readonly saving = signal(false);
  readonly formError = signal('');

  constructor() {
    effect(() => {
      this.auth.activeProjectId();
      this.load();
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .list<Task>('tasks/', {
        project: this.auth.activeProjectId(),
        page_size: 200,
      })
      .subscribe({
        next: (page) => {
          this.tasks.set(page.results);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.api.errorMessage(err));
          this.loading.set(false);
        },
      });
  }

  tasksFor(status: string): Task[] {
    return this.tasks().filter((task) => task.status === status);
  }

  onDragStart(task: Task): void {
    this.dragTask.set(task);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  onDrop(status: string): void {
    const task = this.dragTask();
    if (!task || task.status === status) {
      this.dragTask.set(null);
      return;
    }
    const previous = task.status;
    this.tasks.update((items) => items.map((item) => (item.id === task.id ? { ...item, status } : item)));
    this.api.patch(`tasks/${task.id}/`, { status }).subscribe({
      error: () => {
        this.tasks.update((items) => items.map((item) => (item.id === task.id ? { ...item, status: previous } : item)));
        this.error.set('Failed to update task status.');
      },
    });
    this.dragTask.set(null);
  }

  openForm(): void {
    this.showForm.set(true);
    this.formTitle.set('');
    this.formPriority.set('medium');
    this.formDue.set('');
    this.formError.set('');
  }

  closeForm(): void {
    this.showForm.set(false);
  }

  create(): void {
    const projectId = this.auth.activeProjectId();
    if (!projectId) {
      this.formError.set('Select an active project.');
      return;
    }
    if (!this.formTitle().trim()) {
      this.formError.set('Enter a title.');
      return;
    }
    this.saving.set(true);
    this.formError.set('');
    this.api
      .post<Task>('tasks/', {
        project: projectId,
        title: this.formTitle().trim(),
        priority: this.formPriority(),
        due_date: this.formDue() || null,
        status: 'not_started',
      })
      .subscribe({
        next: (task) => {
          this.tasks.update((items) => [task, ...items]);
          this.saving.set(false);
          this.showForm.set(false);
        },
        error: (err) => {
          this.saving.set(false);
          this.formError.set(this.api.errorMessage(err));
        },
      });
  }

  assigneeName(task: Task): string {
    const user = task.assignee;
    if (!user) return 'Unassigned';
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
    return name || user.email;
  }
}
