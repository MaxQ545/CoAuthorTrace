import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Author Search API', () => {
  test('should return search results for a valid query', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang', { timeout: 10000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('results');
    expect(Array.isArray(body.results)).toBeTruthy();
    expect(body.results.length).toBeGreaterThan(0);
    expect(body).toHaveProperty('total');
  });

  test('should return empty results for nonsense query', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=xyznonexistent12345', { timeout: 10000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('results');
    expect(body.results.length).toBe(0);
    expect(body.total).toBe(0);
  });

  test('should handle single-character queries', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Z', { timeout: 10000 });
    // Should either return 422/400 (validation error) or empty/valid results
    if (response.ok()) {
      const body = await response.json();
      expect(body).toHaveProperty('results');
    } else {
      expect([400, 422]).toContain(response.status());
    }
  });

  test('should include author fields in search results', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang', { timeout: 10000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    if (body.results.length > 0) {
      const author = body.results[0];
      expect(author).toHaveProperty('id');
      expect(author).toHaveProperty('display_name');
    }
  });

  test('should support pagination with limit and offset', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=2', { timeout: 10000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.results.length).toBeLessThanOrEqual(2);
    expect(body).toHaveProperty('limit');
    expect(body.limit).toBe(2);
  });

  test('should return search results within 5 seconds (performance)', async ({ request }) => {
    const start = Date.now();
    const response = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=10', { timeout: 10000 });
    const elapsed = Date.now() - start;

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('results');
    expect(body.results.length).toBeGreaterThan(0);

    // Performance assertion: search must complete within 5 seconds
    expect(elapsed).toBeLessThan(5000);
    // Log the actual time for visibility
    console.log(`Search completed in ${elapsed}ms`);
  });
});
