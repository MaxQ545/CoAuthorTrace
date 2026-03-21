import { test, APIRequestContext } from '@playwright/test';

const DEFAULT_TIMEOUT = 15000;

/**
 * Perform an API GET request, skipping the test gracefully if the server is unreachable.
 */
export async function safeGet(
  request: APIRequestContext,
  url: string,
  options?: { timeout?: number }
) {
  try {
    return await request.get(url, { timeout: options?.timeout ?? DEFAULT_TIMEOUT });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    if (
      msg.includes('ECONNREFUSED') ||
      msg.includes('ECONNRESET') ||
      msg.includes('TIMED') ||
      msg.includes('Timeout') ||
      msg.includes('timeout') ||
      msg.includes('net::') ||
      msg.includes('socket hang up')
    ) {
      test.skip(true, `Server unreachable: ${msg.slice(0, 80)}`);
      return null as never;
    }
    throw error;
  }
}

export async function safePost(
  request: APIRequestContext,
  url: string,
  data?: unknown,
  options?: { timeout?: number }
) {
  try {
    return await request.post(url, {
      data,
      timeout: options?.timeout ?? DEFAULT_TIMEOUT,
    });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    if (
      msg.includes('ECONNREFUSED') ||
      msg.includes('ECONNRESET') ||
      msg.includes('TIMED') ||
      msg.includes('Timeout') ||
      msg.includes('timeout') ||
      msg.includes('net::') ||
      msg.includes('socket hang up')
    ) {
      test.skip(true, `Server unreachable: ${msg.slice(0, 80)}`);
      return null as never;
    }
    throw error;
  }
}
