import { defineConfig, devices } from '@playwright/test';
import 'dotenv/config';

const baseURL =
  process.env.OPENEMR_BASE_URL ?? 'http://localhost:8300';

if (
  !baseURL.startsWith('http://localhost:') &&
  !baseURL.startsWith('https://localhost:')
) {
  throw new Error(
    `Refusing to run OpenEMR UI tests against non-local target: ${baseURL}`,
  );
}

export default defineConfig({
  testDir: './tests/ui',
  fullyParallel: false,
  workers: 1,

  timeout: 30_000,

  expect: {
    timeout: 10_000,
  },

  reporter: [
    ['list'],
    [
      'html',
      {
        outputFolder: 'artifacts/playwright-report',
        open: 'never',
      },
    ],
  ],

  outputDir: 'artifacts/playwright-test-results',

  use: {
    baseURL,

    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',

    actionTimeout: 10_000,
    navigationTimeout: 20_000,
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
