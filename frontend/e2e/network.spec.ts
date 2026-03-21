import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Network API', () => {
  test('should return SSE stream from network expand endpoint', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 10000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    // Network expand is an SSE endpoint; verify it returns 200 and text/event-stream
    const response = await safeGet(request, `/api/v1/network/expand?author_ids=${authorId}&max_depth=1`, { timeout: 30000 });
    expect(response.ok()).toBeTruthy();
    const body = await response.text();
    // SSE stream should contain event types like 'init', 'node', 'complete'
    expect(body).toContain('event:');
    expect(body).toContain('complete');
  });

  test('should return network metrics for an author', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 10000 });
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
