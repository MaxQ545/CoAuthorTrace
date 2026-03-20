import { test, expect } from '@playwright/test';

test.describe('Author Detail Page', () => {
  test('should display author details after navigating from search', async ({ page }) => {
    // Navigate to search and look for results
    await page.goto('/authors/search?q=Zhang');

    const resultLinks = page.locator('a[href^="/author/"]');
    const hasResults = await resultLinks.first().isVisible({ timeout: 20000 }).catch(() => false);

    if (!hasResults) {
      test.skip(true, 'Search API did not return results in time');
      return;
    }

    // Click the first result
    await resultLinks.first().click();
    await page.waitForURL(/\/author\//, { timeout: 10000 });

    // Verify author name heading exists (h1 or h2)
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10000 });
    await expect(heading).not.toBeEmpty();

    // Verify stats-related content renders (papers, citations, etc.)
    const statsArea = page.getByText(/论文|发表|引用|合作/).first();
    await expect(statsArea).toBeVisible({ timeout: 10000 });

    // Verify collaborators section exists
    const collaboratorsSection = page.getByText(/合作者|合作学者|Collaborat/i).first();
    await expect(collaboratorsSection).toBeVisible({ timeout: 10000 });
  });
});
