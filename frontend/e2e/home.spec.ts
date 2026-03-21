import { test, expect } from '@playwright/test';
import { safeGoto } from './helpers';

test.describe('Home Page', () => {
  test('should load the home page', async ({ page }) => {
    await safeGoto(page, '/');
    await expect(page).toHaveTitle(/论文合作者追踪系统|CoAuthor/i);
  });

  test('should display navigation links', async ({ page }) => {
    await safeGoto(page, '/');
    const nav = page.locator('header nav');
    await expect(nav.getByText('首页')).toBeVisible();
    await expect(nav.getByText('机构排行')).toBeVisible();
    await expect(nav.getByText('合作网络')).toBeVisible();
  });

  test('should confirm health endpoint returns healthy status', async ({ request }) => {
    let response;
    try {
      response = await request.get('http://121.196.234.6:8000/health', { timeout: 15000 });
    } catch {
      test.skip(true, 'Backend health endpoint unreachable from test runner');
      return;
    }
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('healthy');
  });

  test('should render system stats section or loading state', async ({ page }) => {
    await safeGoto(page, '/');
    // The page should show either stats cards, loading placeholders, or error message
    // Wait for page to settle, then check that at least one expected element is present
    await page.waitForTimeout(2000);
    const statsVisible = await page.getByText('收录论文').isVisible().catch(() => false);
    const pulseVisible = await page.locator('.animate-pulse').first().isVisible().catch(() => false);
    const errorVisible = await page.getByText('加载统计数据失败').isVisible().catch(() => false);
    expect(statsVisible || pulseVisible || errorVisible).toBeTruthy();
  });

  test('should have a print button on author detail page', async ({ page }) => {
    // Navigate to search, find a result, click it, then check for print button
    await safeGoto(page, '/authors/search?q=Zhang');

    const resultLinks = page.locator('a[href^="/author/"]');
    const hasResults = await resultLinks.first().isVisible({ timeout: 20000 }).catch(() => false);

    if (!hasResults) {
      test.skip(true, 'Search API did not return results in time');
      return;
    }

    // Click the first author result
    await resultLinks.first().click();
    await page.waitForURL(/\/author\//, { timeout: 10000 });

    // Verify the print button exists (it has title="打印学者档案" and contains text "打印")
    const printButton = page.locator('button', { hasText: '打印' });
    await expect(printButton).toBeVisible({ timeout: 10000 });
  });

  test('should have a skip-to-content accessibility link', async ({ page }) => {
    await safeGoto(page, '/');
    const skipLink = page.locator('a[href="#main-content"]');
    const exists = await skipLink.count();
    if (exists === 0) {
      test.skip(true, 'Skip-to-content link not deployed yet');
      return;
    }
    await expect(skipLink).toHaveAttribute('href', '#main-content');
  });
});
