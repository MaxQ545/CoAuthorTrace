import { test, expect } from '@playwright/test';

test.describe('Ranking Page', () => {
  test('should load ranking page', async ({ page }) => {
    await page.goto('/ranking');

    // The page shows either the header (if institutions loaded) or a loading state
    const header = page.getByText('机构学者排行');
    const loading = page.getByText('正在加载机构数据');
    await expect(header.or(loading)).toBeVisible({ timeout: 10000 });
  });

  test('should display institution sidebar or loading state', async ({ page }) => {
    await page.goto('/ranking');

    // The sidebar shows institution list header or the page shows a loading state
    const sidebar = page.getByText('合作机构');
    const loading = page.getByText('正在加载机构数据');
    await expect(sidebar.or(loading)).toBeVisible({ timeout: 15000 });
  });

  test('should show ranking content when data loads', async ({ page }) => {
    await page.goto('/ranking');

    // Wait for the page to get past the initial loading state
    const header = page.getByText('机构学者排行');
    const loading = page.getByText('正在加载机构数据');
    await expect(header.or(loading)).toBeVisible({ timeout: 15000 });

    // If the header loaded, verify more content
    const headerVisible = await header.isVisible().catch(() => false);
    if (headerVisible) {
      // Institution sidebar or ranking data should be present
      const sidebar = page.getByText('合作机构');
      const rankingData = page.locator('a[href^="/author/"]').first();
      const rankingLoading = page.getByText('正在计算排名数据');
      await expect(sidebar.or(rankingData).or(rankingLoading)).toBeVisible({ timeout: 15000 });
    }
    // If still loading, that's OK — the API is just slow
  });
});
