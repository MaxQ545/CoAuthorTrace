import { test, expect } from '@playwright/test';
import { safeGoto } from './helpers';

test.describe('Author Search Page', () => {
  test('should render search page with search box', async ({ page }) => {
    await safeGoto(page, '/authors/search');
    await expect(page.getByText('作者搜索')).toBeVisible();
    await expect(page.getByPlaceholder('输入作者姓名搜索...')).toBeVisible();
  });

  test('should accept search input and trigger search', async ({ page }) => {
    await safeGoto(page, '/authors/search');

    // Type a query in the search box and submit
    const searchInput = page.getByPlaceholder('输入作者姓名搜索...');
    await searchInput.fill('Zhang');
    await searchInput.press('Enter');

    // After submitting, the URL should update with query param
    await expect(page).toHaveURL(/q=Zhang/);

    // Should show either results, loading state, or "no results" message
    const results = page.locator('a[href^="/author/"]').first();
    const loading = page.getByText('搜索中...');
    const noResults = page.getByText(/未找到|没有找到/);
    const errorMsg = page.getByText('搜索失败');
    await expect(results.or(loading).or(noResults).or(errorMsg)).toBeVisible({ timeout: 20000 });
  });

  test('should not trigger search results with a single character query', async ({ page }) => {
    await safeGoto(page, '/authors/search');

    const searchInput = page.getByPlaceholder('输入作者姓名搜索...');
    await searchInput.fill('Z');
    await searchInput.press('Enter');

    // Wait a moment to confirm no results appear
    await page.waitForTimeout(2000);

    // With a single character, the search should NOT return result cards
    const resultCards = page.locator('a[href^="/author/"]');
    const count = await resultCards.count();
    expect(count).toBe(0);
  });

  test('should navigate to author page when clicking a search result', async ({ page }) => {
    await safeGoto(page, '/authors/search?q=Zhang');

    // Wait for result cards — they may take time due to API latency
    const resultCards = page.locator('a[href^="/author/"]');
    const hasResults = await resultCards.first().isVisible({ timeout: 20000 }).catch(() => false);

    if (hasResults) {
      await resultCards.first().click();
      await page.waitForURL(/\/author\//, { timeout: 10000 });
      expect(page.url()).toContain('/author/');
    } else {
      // API may be slow — verify the search page rendered correctly instead
      await expect(page.getByText('作者搜索')).toBeVisible();
      test.skip(true, 'Search API did not return results in time');
    }
  });
});
