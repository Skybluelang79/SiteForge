import { describe, expect, it } from 'vitest';

import { API_ROOT, CLOUDFLARE_ACCESS_ENABLED } from './auth.service';

describe('API_ROOT', () => {
  it('resolves to a non-empty API path', () => {
    expect(typeof API_ROOT).toBe('string');
    expect(API_ROOT.length).toBeGreaterThan(0);
  });

  it('keeps Cloudflare Access disabled without a runtime flag', () => {
    expect(CLOUDFLARE_ACCESS_ENABLED).toBe(false);
  });
});
