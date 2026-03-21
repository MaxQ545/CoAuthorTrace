import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Author Detail API', () => {
  test('should return author detail by ID from search', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 30000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    const response = await safeGet(request, `/api/v1/authors/${authorId}`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('display_name');
    expect(body).toHaveProperty('id');
  });

  test('should return collaborators for an author', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 30000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    const response = await safeGet(request, `/api/v1/authors/${authorId}/collaborators`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(Array.isArray(body)).toBeTruthy();
  });

  test('should return error for non-existent author', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/nonexistent-id-999');
    // Server returns 422 (validation) or 404 (not found) for invalid author IDs
    expect([404, 422]).toContain(response.status());
  });

  test('should return publication timeline', async ({ request }) => {
    const searchResponse = await safeGet(request, '/api/v1/authors/search?q=Zhang&limit=1', { timeout: 30000 });
    expect(searchResponse.ok()).toBeTruthy();
    const searchBody = await searchResponse.json();

    if (!searchBody.results?.length) {
      test.skip(true, 'No authors found in search');
      return;
    }

    const authorId = searchBody.results[0].id;
    const response = await safeGet(request, `/api/v1/authors/${authorId}/publication-timeline`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(Array.isArray(body)).toBeTruthy();
  });
});
