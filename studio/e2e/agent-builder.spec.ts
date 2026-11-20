import { expect, test, type BrowserContext } from "@playwright/test";
import { sealData } from "iron-session";
import path from "node:path";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const captureDirectory = path.resolve(process.cwd(), "../hamza_local/phase13h-qa");

async function authenticate(context: BrowserContext) {
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=user-two`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: "user-two", email: "user-two@example.test", firstName: "Offline", lastName: "User" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ context }) => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
});

test("resumes onboarding and completes the guided agent lifecycle", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page.getByRole("heading", { name: "Complete workspace setup" })).toBeVisible();
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-dashboard-desktop-20261107.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
      (sidebar) => sidebar.getBoundingClientRect().right <= 0,
    )).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-dashboard-mobile-390-20261107.png"), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 720 });
    await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "false");
    await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
      (sidebar) => Math.round(sidebar.getBoundingClientRect().width),
    )).toBe(248);
  }
  await page.getByRole("link", { name: "Setup", exact: true }).click();
  await expect(page).toHaveURL(/\/onboarding$/);

  await expect(page.getByLabel("Business name")).toHaveValue("Hamzi Stores");
  await expect(page.getByText("Operating region is required.")).toBeVisible();
  if (process.env.CAPTURE_PHASE13H === "1") {
    await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
      (sidebar) => Math.round(sidebar.getBoundingClientRect().width),
    )).toBe(248);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-onboarding-desktop-20261107.png") });
  }
  await page.getByLabel("Operating region").fill("Pakistan");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByText("Onboarding saved.")).toBeVisible();

  await page.getByRole("link", { name: "Build", exact: true }).click();
  await expect(page).toHaveURL(/\/agents$/);
  await page.getByRole("link", { name: "Create agent" }).click();
  await expect(page).toHaveURL(/\/agents\/new$/);
  await expect(page.getByRole("heading", { name: "Create an agent" })).toBeVisible();
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.evaluate(() => window.scrollTo({ top: 0 }));
    await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
      (sidebar) => Math.round(sidebar.getBoundingClientRect().width),
    )).toBe(248);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-agent-create-desktop-20261107.png") });
  }
  await page.getByLabel(/Retail customer care/).check();
  await page.getByLabel("Agent name").fill("Store assistant");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("link", { name: "Continue building" }).click();

  await page.getByLabel("Description").fill("Handles order and return questions");
  await expect(page.getByText(/Saved at revision 2/)).toBeVisible();
  await page.getByRole("button", { name: "Check readiness" }).click();
  await expect(page.getByText("Ready to publish.")).toBeVisible();
  await page.getByRole("button", { name: "Publish agent" }).click();
  await expect(page.getByText("Published version 1.")).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Restore version 1" }).click();
  await expect(page.getByText("Version 1 remains immutable; its snapshot was copied into a new draft.")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/33333333-3333-4333-8333-/);
});

test("keeps viewer workspaces read-only without exposing internal identifiers", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Beta workspace/ }).click();
  await page.getByRole("link", { name: "Build", exact: true }).click();
  await expect(page).toHaveURL(/\/agents$/);
  await page.getByRole("link", { name: "View agent" }).click();
  await expect(page).toHaveURL(/\/agents\/[0-9a-f-]+\/build$/);

  await expect(page.getByText("You have view-only access.")).toBeVisible();
  await expect(page.getByLabel("Agent name")).toBeDisabled();
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByLabel("System prompt")).toBeDisabled();
  await expect(page.locator("body")).not.toContainText("44444444-4444-4444-8444-444444444444");
});
