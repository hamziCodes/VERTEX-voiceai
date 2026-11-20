import { defineConfig, devices } from "@playwright/test";

const appPort = Number(process.env.WAVIA_E2E_APP_PORT ?? "3100");
const fixturePort = Number(process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211");
const appBaseUrl = `http://127.0.0.1:${appPort}`;
const fixtureBaseUrl = `http://127.0.0.1:${fixturePort}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // The offline control-plane fixture is intentionally stateful; serialize journeys so
  // one test's reset cannot invalidate another test's tenant or agent lifecycle.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: appBaseUrl,
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "node e2e/fixtures/offline-auth-server.mjs",
      url: `${fixtureBaseUrl}/health`,
      reuseExistingServer: !process.env.CI,
      env: {
        WAVIA_E2E_APP_PORT: String(appPort),
        WAVIA_E2E_FIXTURE_PORT: String(fixturePort),
      },
    },
    {
      command: `node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port ${appPort}`,
      url: appBaseUrl,
      reuseExistingServer: !process.env.CI,
      env: {
        WORKOS_CLIENT_ID: "client_offline_test",
        WORKOS_COOKIE_PASSWORD: `test-${"x".repeat(32)}`,
        NEXT_PUBLIC_WORKOS_REDIRECT_URI: `${appBaseUrl}/auth/callback`,
        WORKOS_API_HOSTNAME: "127.0.0.1",
        WORKOS_API_HTTPS: "false",
        WORKOS_API_PORT: String(fixturePort),
        WORKOS_ISSUER: `${fixtureBaseUrl}/`,
        WAVIA_CONTROL_PLANE_URL: fixtureBaseUrl,
        WAVIA_VOICE_TEST_MODE: "mock",
      },
    },
  ],
});
