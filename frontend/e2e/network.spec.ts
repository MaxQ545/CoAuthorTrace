import { test, expect } from '@playwright/test';
import { safeGoto } from './helpers';

test.describe('Network Page', () => {
  test('should load with author selection UI', async ({ page }) => {
    await safeGoto(page, '/network');

    // Verify the page loads with network-related UI elements
    // The page should show author selection / seed author interface
    const networkUI = page.locator('text=/合作网络|选择|作者|构建|网络/').first();
    await expect(networkUI).toBeVisible({ timeout: 10000 });
  });

  test('should display network configuration controls', async ({ page }) => {
    await safeGoto(page, '/network');

    // The page should have a button to start building the network
    const buildButton = page.locator('button').filter({ hasText: /构建|开始|Build|Start/i }).first();
    await expect(buildButton).toBeVisible({ timeout: 10000 });
  });
});
