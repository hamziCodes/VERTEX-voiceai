import path from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const captureDirectory = path.resolve(process.cwd(), "../hamza_local/phase13h-qa");
// Screenshots keep the caret: hiding it injects styles before hydration and React reports a mismatch.
const capture = process.env.CAPTURE_PHASE13H === "1";

const ROUTES: ReadonlyArray<{ path: string; heading: RegExp; name: string }> = [
  { path: "/dashboard", heading: /./, name: "dashboard" },
  { path: "/onboarding", heading: /./, name: "onboarding" },
  { path: "/agents/new", heading: /./, name: "agent-create" },
  { path: "/test", heading: /^Test an agent$/, name: "test-selector" },
  { path: "/settings", heading: /^Settings$/, name: "settings" },
  { path: "/settings/members", heading: /^Members$/, name: "members" },
];

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

async function selectAlpha(page: Page) {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function noHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test.beforeEach(async ({ context }) => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
});

test("customer foundation routes render without overflow or console errors at desktop width", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/workspaces");
  await noHorizontalOverflow(page);
  if (capture) await page.screenshot({ path: path.join(captureDirectory, "phase13h-qa-workspaces-desktop-20261112.png"), caret: "initial" });
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  for (const route of ROUTES) {
    await page.goto(route.path);
    await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Workspace" })).toBeVisible();
    await noHorizontalOverflow(page);
    if (capture) await page.screenshot({ path: path.join(captureDirectory, `phase13h-qa-${route.name}-desktop-20261112.png`), caret: "initial" });
  }
  expect(errors).toEqual([]);
});

test("customer foundation routes stay usable at 390px with a dismissible navigation drawer", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspaces");
  await noHorizontalOverflow(page);
  if (capture) await page.screenshot({ path: path.join(captureDirectory, "phase13h-qa-workspaces-mobile-390-20261112.png"), caret: "initial" });
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  for (const route of ROUTES) {
    await page.goto(route.path);
    await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();
    await noHorizontalOverflow(page);
    // The closed drawer is hidden from assistive technology and does not cover content.
    await expect(page.getByRole("navigation", { name: "Workspace" })).toBeHidden();
    if (capture) await page.screenshot({ path: path.join(captureDirectory, `phase13h-qa-${route.name}-mobile-390-20261112.png`), caret: "initial" });
  }

  const trigger = page.getByRole("button", { name: "Open navigation" });
  await trigger.click();
  const navigation = page.getByRole("navigation", { name: "Workspace" });
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  if (capture) {
    // Let the 200ms slide-in finish so the capture shows the resting drawer.
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-qa-drawer-mobile-390-20261112.png"), caret: "initial" });
  }
  await page.keyboard.press("Escape");
  await expect(navigation).toBeHidden();
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeFocused();
  expect(errors).toEqual([]);
});

test("desktop sidebar collapse persists across reloads and navigation keeps visible keyboard focus", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await selectAlpha(page);
  await page.goto("/settings/members");

  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "true");
  await page.reload();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "true");
  await expect(page.getByRole("navigation", { name: "Workspace" }).getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 1, name: "Members" })).toBeVisible();
  if (capture) await page.screenshot({ path: path.join(captureDirectory, "phase13h-qa-members-collapsed-desktop-20261112.png"), caret: "initial" });
  // Only the non-sensitive versioned layout preference is stored.
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(["wavia:studio:sidebar:v1"]);

  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect(page.locator(".studio-sidebar")).toHaveAttribute("data-collapsed", "false");
  // Let the 200ms width transition settle before measuring focus and capturing.
  await page.waitForTimeout(400);

  // Keyboard users reach the sidebar and see a focus indicator.
  await page.locator("body").focus();
  let focusedNav = false;
  for (let index = 0; index < 12 && !focusedNav; index += 1) {
    await page.keyboard.press("Tab");
    focusedNav = await page.evaluate(() => document.activeElement?.classList.contains("studio-nav-link") ?? false);
  }
  expect(focusedNav).toBe(true);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
  if (capture) await page.screenshot({ path: path.join(captureDirectory, "phase13h-qa-keyboard-focus-desktop-20261112.png"), caret: "initial" });
  expect(errors).toEqual([]);
});
