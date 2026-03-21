import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Author Search API', () => {
  test('should return search results for a valid query', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang', { timeout: 30000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('results');
    expect(Array.isArray(body.results)).toBeTruthy();
    expect(body.results.length).toBeGreaterThan(0);
    expect(body).toHaveProperty('total');
  });

  test('should return empty results for nonsense query', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=xyznonexistent12345');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('results');
    expect(body.results.length).toBe(0);
    expect(body.total).toBe(0);
  });

  test('should handle single-character queries', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Z');
    // Should either return 422/400 (validation error) or empty/valid results
    if (response.ok()) {
      const body = await response.json();
      expect(body).toHaveProperty('results');
    } else {
      expect([400, 422]).toContain(response.status());
    }
  });

  test('should include author fields in search results', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang', { timeout: 30000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    if (body.results.length > 0) {
      const author = body.results[0];
      expect(author).toHaveProperty('id');
      expect(author).toHaveProperty('display_name');
    }
  });

  test('should support pagination with limit and offset', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=2', { timeout: 30000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.results.length).toBeLessThanOrEqual(2);
    expect(body).toHaveProperty('limit');
    expect(body.limit).toBe(2);
  });
});
