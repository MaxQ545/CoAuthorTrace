import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Ranking & Institutions API', () => {
  test('should return list of institutions', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/institutions');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('institutions');
    expect(Array.isArray(body.institutions)).toBeTruthy();
    expect(body.institutions.length).toBeGreaterThan(0);
  });

  test('should return institution ranking data for a small institution', async ({ request }) => {
    const instResponse = await safeGet(request, '/api/v1/authors/institutions');
    expect(instResponse.ok()).toBeTruthy();
    const instBody = await instResponse.json();

    if (instBody.institutions.length === 0) {
      test.skip(true, 'No institutions available');
      return;
    }

    const sorted = [...instBody.institutions].sort((a: { author_count: number }, b: { author_count: number }) => a.author_count - b.author_count);
    const institutionId = sorted[0].id;

    const response = await safeGet(
      request,
      `/api/v1/authors/ranking/by-institution?institution_id=${institutionId}&limit=1`,
      { timeout: 30000 }
    );
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('authors');
    expect(Array.isArray(body.authors)).toBeTruthy();
  });

  test('should include author details in ranking results', async ({ request }) => {
    const instResponse = await safeGet(request, '/api/v1/authors/institutions');
    expect(instResponse.ok()).toBeTruthy();
    const instBody = await instResponse.json();

    if (instBody.institutions.length === 0) {
      test.skip(true, 'No institutions available');
      return;
    }

    const sorted = [...instBody.institutions].sort((a: { author_count: number }, b: { author_count: number }) => a.author_count - b.author_count);
    const institutionId = sorted[0].id;

    const response = await safeGet(
      request,
      `/api/v1/authors/ranking/by-institution?institution_id=${institutionId}&limit=1`,
      { timeout: 30000 }
    );
    expect(response.ok()).toBeTruthy();
    const body = await response.json();

    if (body.authors.length > 0) {
      const author = body.authors[0];
      expect(author).toHaveProperty('id');
      expect(author).toHaveProperty('display_name');
      expect(author).toHaveProperty('works_count');
    }
  });

  test('should include institution metadata in response', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/authors/institutions');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    if (body.institutions.length > 0) {
      const inst = body.institutions[0];
      expect(inst).toHaveProperty('name');
      expect(inst).toHaveProperty('id');
      expect(inst).toHaveProperty('author_count');
    }
  });
});
