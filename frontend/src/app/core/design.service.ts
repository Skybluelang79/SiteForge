import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { ApiService } from './api.service';

export interface CanvasBoard {
  id: string;
  project: string;
  name: string;
  state: unknown;
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class DesignService {
  private readonly api = inject(ApiService);

  listBoards(projectId: string): Observable<CanvasBoard[]> {
    return this.api.list<CanvasBoard>('canvas-boards/', { project: projectId }).pipe(map((page) => page.results));
  }

  createBoard(body: { project: string; name: string; state: unknown }): Observable<CanvasBoard> {
    return this.api.post<CanvasBoard>('canvas-boards/', body);
  }

  updateBoard(id: string, body: Partial<Pick<CanvasBoard, 'name' | 'state'>>): Observable<CanvasBoard> {
    return this.api.patch<CanvasBoard>(`canvas-boards/${id}/`, body);
  }
}
