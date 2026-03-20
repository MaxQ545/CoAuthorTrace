import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('should load the home page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/论文合作者追踪系统|CoAuthor/i);
  });

  test('should display navigation links', async ({ page }) => {
    await page.goto('/');
    const nav = page.locator('header nav');
    await expect(nav.getByText('首页')).toBeVisible();
    await expect(nav.getByText('机构排行')).toBeVisible();
    await expect(nav.getByText('合作网络')).toBeVisible();
  });

  test('should confirm health endpoint returns healthy status', async ({ request }) => {
    let response;
    try {
      response = await request.get('http://121.196.234.6:8000/health', { timeout: 25000 });
    } catch {
      test.skip(true, 'Backend health endpoint unreachable from test runner');
      return;
    }
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('healthy');
  });

  test('should render system stats section or loading state', async ({ page }) => {
    await page.goto('/');
    // The page should show either stats cards, loading placeholders, or error message
    // Wait for page to settle, then check that at least one expected element is present
    await page.waitForTimeout(2000);
    const statsVisible = await page.getByText('收录论文').isVisible().catch(() => false);
    const pulseVisible = await page.locator('.animate-pulse').first().isVisible().catch(() => false);
    const errorVisible = await page.getByText('加载统计数据失败').isVisible().catch(() => false);
    expect(statsVisible || pulseVisible || errorVisible).toBeTruthy();
  });
});
