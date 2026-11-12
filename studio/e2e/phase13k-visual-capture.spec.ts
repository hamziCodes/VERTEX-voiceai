import path from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

// Capture-only pass for the Phase 13K visual consistency review. Skipped unless
// CAPTURE_PHASE13K=1; images go to the gitignored hamza_local/phase13k-qa folder.
const capture = process.env.CAPTURE_PHASE13K === "1";
const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const directory = path.resolve(process.cwd(), "../hamza_local/phase13k-qa");
const WIDTHS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
  { name: "mobile-320", width: 320, height: 700 },
] as const;

const CUSTOMER = [
  ["workspaces", "/workspaces"],
  ["dashboard", "/dashboard"],
  ["onboarding", "/onboarding"],
  ["agents", "/agents"],
  ["agent-create", "/agents/new"],
  ["test-selector", "/test"],
  ["knowledge", "/knowledge"],
  ["channels-web", "/channels/web"],
  ["channels-telephony", "/channels/telephony"],
  ["conversations", "/conversations"],
  ["conversation-detail", "/conversations/91111111-1111-4111-8111-111111111111"],
  ["api-keys", "/developers/api-keys"],
  ["settings", "/settings"],
  ["members", "/settings/members"],
  ["providers", "/settings/providers"],
  ["usage", "/settings/usage"],
  ["audit", "/settings/audit"],
] as const;

const ADMIN = [
  ["admin-overview", "/admin"],
  ["admin-tenants", "/admin/tenants"],
  ["admin-tenant-detail", "/admin/tenants/22222222-2222-4222-8222-222222222222"],
  ["admin-support-sessions", "/admin/support-sessions"],
  ["admin-operations", "/admin/operations"],
  ["admin-staff", "/admin/staff"],
  ["admin-audit", "/admin/audit"],
] as const;

async function authenticate(context: BrowserContext, subject: string) {
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=${subject}`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: subject, email: `${subject}@example.test`, firstName: "Offline", lastName: "User" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

async function shoot(page: Page, name: string, viewport: string) {
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.screenshot({ path: path.join(directory, `phase13k-qa-${name}-${viewport}-20261112.png`), caret: "initial" });
}

test.skip(!capture, "Set CAPTURE_PHASE13K=1 to capture the visual review set.");

test.beforeEach(async () => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
});

for (const viewport of WIDTHS) {
  test(`customer routes at ${viewport.name}`, async ({ context, page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await authenticate(context, "user-two");
    await page.goto("/workspaces");
    await page.getByRole("button", { name: /Alpha workspace/ }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    for (const [name, route] of CUSTOMER) {
      await page.goto(route);
      await shoot(page, name, viewport.name);
    }
  });

  test(`internal routes at ${viewport.name}`, async ({ context, page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await authenticate(context, "user-platform-admin");
    for (const [name, route] of ADMIN) {
      await page.goto(route);
      await shoot(page, name, viewport.name);
    }
    await page.goto("/admin/tenants/22222222-2222-4222-8222-222222222222");
    await page.getByRole("button", { name: "Start support session" }).click();
    const dialog = page.getByRole("dialog", { name: "Start a support session" });
    await dialog.getByLabel("Reason").fill("Visual review of the support view");
    await dialog.getByRole("checkbox", { name: /Readiness/ }).check();
    await page.screenshot({ path: path.join(directory, `phase13k-qa-admin-start-dialog-${viewport.name}-20261112.png`), caret: "initial" });
    await dialog.getByRole("button", { name: "Start session" }).click();
    await expect(page.getByRole("region", { name: "Support session" })).toBeVisible();
    await shoot(page, "admin-support-session", viewport.name);
    await page.screenshot({ fullPage: true, path: path.join(directory, `phase13k-qa-admin-support-session-full-${viewport.name}-20261112.png`), caret: "initial" });
  });
}
