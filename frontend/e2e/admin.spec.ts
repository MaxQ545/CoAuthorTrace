import { test, expect } from '@playwright/test';

test.describe('Admin Login Page', () => {
  test('should render login form', async ({ page }) => {
    await page.goto('/admin/login');

    // Verify login form elements
    await expect(page.getByText('Admin Login')).toBeVisible({ timeout: 10000 });
    await expect(page.getByPlaceholder('Enter admin password')).toBeVisible();
    await expect(page.getByRole('button', { name: /Sign In/i })).toBeVisible();
  });

  test('should have disabled submit button when password is empty', async ({ page }) => {
    await page.goto('/admin/login');

    // The submit button should be disabled when password field is empty
    const submitButton = page.getByRole('button', { name: /Sign In/i });
    await expect(submitButton).toBeDisabled();
  });

  test('should enable submit button and attempt login with password', async ({ page }) => {
    await page.goto('/admin/login');

    // Type a password — button should become enabled
    const passwordInput = page.getByPlaceholder('Enter admin password');
    await passwordInput.fill('wrongpassword');

    const submitButton = page.getByRole('button', { name: /Sign In/i });
    await expect(submitButton).toBeEnabled();

    // Click submit — it should show "Signing in..." or error feedback
    await submitButton.click();

    // Verify the form responded to the click (either shows loading or error)
    const signingIn = page.getByText('Signing in...');
    const errorMessage = page.locator('.text-red-500');
    await expect(signingIn.or(errorMessage)).toBeVisible({ timeout: 5000 });
  });
});
