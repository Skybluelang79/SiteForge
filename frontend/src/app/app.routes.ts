import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { RESOURCE_PAGES } from './features/resources/resource-config';

const resourceRoutes: Routes = Object.entries(RESOURCE_PAGES).map(([path, config]) => ({
  path,
  data: { resource: config },
  loadComponent: () =>
    import('./features/resources/resource-list.component').then((m) => m.ResourceListComponent),
}));

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./features/login/login.component').then((m) => m.LoginComponent) },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'projects',
        loadComponent: () =>
          import('./features/projects/projects.component').then((m) => m.ProjectsComponent),
      },
      {
        path: 'projects/:id',
        loadComponent: () =>
          import('./features/projects/project-detail.component').then((m) => m.ProjectDetailComponent),
      },
      {
        path: 'profile',
        loadComponent: () => import('./features/profile/profile.component').then((m) => m.ProfileComponent),
      },
      {
        path: 'tasks/board',
        loadComponent: () => import('./features/tasks/task-board.component').then((m) => m.TaskBoardComponent),
      },
      {
        path: 'financials/workspace',
        loadComponent: () => import('./features/financials/financials-workspace.component').then((m) => m.FinancialsWorkspaceComponent),
      },
      {
        path: 'organization',
        loadComponent: () => import('./features/organization/organization.component').then((m) => m.OrganizationComponent),
      },
      {
        path: 'field/logs/:id',
        loadComponent: () => import('./features/field/daily-log-detail.component').then((m) => m.DailyLogDetailComponent),
      },
      {
        path: 'quality/punch-lists/:id',
        loadComponent: () => import('./features/quality/punch-list-detail.component').then((m) => m.PunchListDetailComponent),
      },
      {
        path: 'rfis/:id',
        loadComponent: () => import('./features/rfis/rfi-detail.component').then((m) => m.RfiDetailComponent),
      },
      {
        path: 'submittals/:id',
        loadComponent: () => import('./features/rfis/submittal-detail.component').then((m) => m.SubmittalDetailComponent),
      },
      ...resourceRoutes,
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
