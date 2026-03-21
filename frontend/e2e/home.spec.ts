import { test, expect } from '@playwright/test';
import { safeGet } from './helpers';

test.describe('Root & Health Endpoints', () => {
  test('should return API info from root endpoint', async ({ request }) => {
    const response = await safeGet(request, '/');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.name).toContain('Coauthor Tracing API');
    expect(body.version).toBeDefined();
    expect(body.docs).toBe('/api/docs');
  });

  test('should confirm health endpoint returns healthy status', async ({ request }) => {
    const response = await safeGet(request, '/health');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('healthy');
  });

  test('should serve OpenAPI docs endpoint', async ({ request }) => {
    const response = await safeGet(request, '/api/docs');
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    expect(text).toContain('swagger');
  });

  test('should serve OpenAPI JSON schema', async ({ request }) => {
    const response = await safeGet(request, '/api/openapi.json');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.openapi).toBeDefined();
    expect(body.info.title).toContain('Coauthor Tracing');
    expect(body.paths).toBeDefined();
  });

  test('should return system status with database info', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/system/status');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty('status');
    expect(body).toHaveProperty('database');
    expect(body.database).toHaveProperty('total_authors');
    expect(body.database).toHaveProperty('total_works');
    expect(body.database.total_authors).toBeGreaterThan(0);
  });
});
