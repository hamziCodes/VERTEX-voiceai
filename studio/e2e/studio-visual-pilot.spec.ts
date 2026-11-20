import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";
import path from "node:path";

const cookiePassword = `test-${"x".repeat(32)}`;
const captureDirectory = path.resolve(process.cwd(), "../hamza_local/phase13h-qa");
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;

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

async function expectNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious")).toEqual([]);
}

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ context }) => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
});

test("verifies the Agent Directory and Persona Editor pilot at desktop and mobile widths", async ({ page }) => {
  await page.goto("/workspaces");
  await page.evaluate(() => localStorage.removeItem("wavia:studio:sidebar:v1"));
  await page.reload();
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("link", { name: "Build" }).click();

  await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();
  await expect(page.getByText("No agents yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Create agent" })).toHaveCount(1);
  await expectNoOverflow(page);

  await page.getByRole("link", { name: "Create agent" }).click();
  await page.getByLabel(/Retail customer care/).check();
  await page.getByLabel("Agent name").fill("Store assistant");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("link", { name: "Continue building" }).click();
  await page.getByLabel("Description").fill("Handles order and return questions");
  await expect(page.getByRole("status", { name: "Draft save status" })).toBeVisible();
  await expect(page.getByText(/Saved at revision 2/)).toBeAttached();

  await expect(page.getByRole("navigation", { name: "Agent workspace" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Persona" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("link", { name: "Test sandbox" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tools" })).toHaveCount(0);
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByText(/Tenant data stays isolated/)).toBeVisible();
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "false");
  await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
    (sidebar) => Math.round(sidebar.getBoundingClientRect().width),
  )).toBe(248);
  await expectNoOverflow(page);
  await expectNoSeriousAccessibilityViolations(page);

  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.evaluate(() => window.scrollTo({ top: 0 }));
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-persona-desktop-20261107.png"), fullPage: true });
  }

  await page.goto("/agents");
  await expect(page.getByRole("cell", { name: /Store assistant/ })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search agents" }).fill("missing");
  await expect(page.getByText("No agents match these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText("Store assistant")).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.reload();
  await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Wavia Studio", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Collapse sidebar" })).toBeFocused();
  await expect(page.locator(".studio-mobile-nav-trigger")).toHaveCount(1);
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "true");
  expect(await page.evaluate(() => localStorage.getItem("wavia:studio:sidebar:v1"))).toBe("collapsed");
  await page.reload();
  expect(await page.evaluate(() => localStorage.getItem("wavia:studio:sidebar:v1"))).toBe("collapsed");
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "true");
  await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();

  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-agents-desktop-20261107.png"), fullPage: true });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileTrigger = page.getByRole("button", { name: "Open navigation" });
  await mobileTrigger.click();
  await expect(page.getByRole("button", { name: "Close navigation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(mobileTrigger).toBeFocused();
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-mobile-open", "false");
  await expect.poll(async () => page.locator(".studio-sidebar").evaluate(
    (sidebar) => sidebar.getBoundingClientRect().right <= 0,
  )).toBe(true);
  await expectNoOverflow(page);
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-agents-mobile-390-20261107.png"), fullPage: true });
  }

  await page.getByRole("link", { name: "Open builder" }).click();
  await expect(page.getByRole("heading", { name: /Build Store assistant/ })).toBeVisible();
  await expectNoOverflow(page);
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-persona-mobile-390-20261107.png"), fullPage: true });
  }

  await page.setViewportSize({ width: 320, height: 800 });
  await expectNoOverflow(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByLabel("Agent name")).toBeEditable();
});
