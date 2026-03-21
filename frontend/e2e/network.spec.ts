import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Network API', () => {
  test('should return network expand data for an author', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 30000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    const response = await safeGet(request, `/api/v1/network/expand?author_id=${authorId}`, { timeout: 45000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('nodes');
    expect(body).toHaveProperty('edges');
    expect(Array.isArray(body.nodes)).toBeTruthy();
    expect(Array.isArray(body.edges)).toBeTruthy();
  });

  test('should return network metrics for an author', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 30000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    const response = await safeGet(request, `/api/v1/authors/${authorId}/network-metrics`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toBeDefined();
  });
});
