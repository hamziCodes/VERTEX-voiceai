import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "node e2e/fixtures/offline-auth-server.mjs",
      url: "http://127.0.0.1:3211/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: !process.env.CI,
      env: {
        WORKOS_CLIENT_ID: "client_offline_test",
        WORKOS_COOKIE_PASSWORD: `test-${"x".repeat(32)}`,
        NEXT_PUBLIC_WORKOS_REDIRECT_URI: "http://127.0.0.1:3100/auth/callback",
        WORKOS_API_HOSTNAME: "127.0.0.1",
        WORKOS_API_HTTPS: "false",
        WORKOS_API_PORT: "3211",
        WORKOS_ISSUER: "http://127.0.0.1:3211/",
        WAVIA_CONTROL_PLANE_URL: "http://127.0.0.1:3211",
      },
    },
  ],
});
