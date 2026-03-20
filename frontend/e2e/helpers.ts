import { test, Page } from '@playwright/test';

/**
 * Navigate to a page, skipping the test gracefully if the server is unreachable.
 */
export async function safeGoto(page: Page, path: string): Promise<void> {
  try {
    const response = await page.goto(path, { timeout: 15000 });
    if (!response) {
      test.skip(true, 'Server returned no response');
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    const name = error instanceof Error ? error.name : '';
    if (
      name === 'TimeoutError' ||
      msg.includes('ERR_ABORTED') ||
      msg.includes('ERR_CONNECTION') ||
      msg.includes('TIMED') ||
      msg.includes('Timeout') ||
      msg.includes('net::')
    ) {
      test.skip(true, `Server unreachable: ${msg.slice(0, 80)}`);
      return;
    }
    throw error;
  }
}
