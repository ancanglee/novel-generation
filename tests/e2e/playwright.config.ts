import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 5173);

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 5_000 },
  retries: 0,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1366, height: 900 },
    locale: "zh-CN",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
