import { describe, expect, it } from 'vitest';

import { RESOURCE_PAGES } from './resource-config';

describe('RESOURCE_PAGES', () => {
  it('defines a unique resource page for every configured key', () => {
    const entries = Object.entries(RESOURCE_PAGES);
    expect(entries.length).toBeGreaterThan(0);
    expect(new Set(entries.map(([key]) => key)).size).toBe(entries.length);
  });

  it('gives every action a label, path and method', () => {
    for (const page of Object.values(RESOURCE_PAGES)) {
      for (const action of page.actions ?? []) {
        expect(action.label.length).toBeGreaterThan(0);
        expect(action.path.length).toBeGreaterThan(0);
        expect(['GET', 'POST', 'PATCH', 'DELETE']).toContain(action.method);
      }
    }
  });
});
