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

  test('should render system stats section or loading state', async ({ page }) => {
    await page.goto('/');
    // The page should show either stats cards, loading placeholders, or error message
    const statsText = page.getByText(/收录论文|科研学者|合作关系/);
    const loadingPulse = page.locator('.animate-pulse').first();
    const errorMsg = page.getByText('加载统计数据失败');
    await expect(statsText.first().or(loadingPulse).or(errorMsg)).toBeVisible({ timeout: 10000 });
  });
});
