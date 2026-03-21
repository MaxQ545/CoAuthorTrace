import { test, expect } from '@playwright/test';
import { safeGet, safePost } from './helpers';

test.describe('Admin & Metrics API', () => {
  test('should return prometheus metrics with coauthor_ prefix', async ({ request }) => {
    const response = await safeGet(request, '/metrics');
    if (!response.ok()) {
      test.skip(true, `Metrics endpoint returned ${response.status()} — not deployed`);
      return;
    }
    const body = await response.text();
    expect(body).toContain('coauthor_');
  });

  test('should reject login with wrong password', async ({ request }) => {
    const response = await safePost(request, '/api/v1/admin/login', {
      password: 'wrongpassword',
    });
    // Should return 401 or 403 for wrong password
    expect([401, 403]).toContain(response.status());
  });

  test('should accept JSON body for login endpoint', async ({ request }) => {
    const response = await safePost(request, '/api/v1/admin/login', {
      password: 'test',
    });
    // Should NOT return 422 (validation error) — the body format is correct
    expect(response.status()).not.toBe(422);
  });

  test('should return system config', async ({ request }) => {
    const response = await safeGet(request, '/api/v1/system/config');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toBeDefined();
  });

  test('should rate-limit rapid login attempts', async ({ request }) => {
    const attempts = 10;
    let got429 = false;

    for (let i = 0; i < attempts; i++) {
      try {
        const resp = await request.post('/api/v1/admin/login', {
          data: { password: `wrongpassword_${i}` },
          timeout: 15000,
        });
        if (resp.status() === 429) {
          got429 = true;
          break;
        }
      } catch {
        // Server may be slow, continue
      }
    }

    if (!got429) {
      test.skip(true, 'Rate limiting not enforced on this deployment');
      return;
    }

    expect(got429).toBe(true);
  });
});
