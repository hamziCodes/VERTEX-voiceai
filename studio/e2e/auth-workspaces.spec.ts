import { expect, test, type BrowserContext } from "@playwright/test";
import { sealData } from "iron-session";
import path from "node:path";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const captureDirectory = path.resolve(process.cwd(), "../hamza_local/phase13h-qa");

async function authenticate(context: BrowserContext, subject: string, expired = false) {
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=${subject}&expired=${expired ? "1" : "0"}`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: subject, email: `${subject}@example.test`, firstName: "Offline", lastName: "User" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

test("public sign-in starts no provider call before user confirmation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Build and operate your voice agents" })).toBeVisible();
  await page.getByRole("link", { name: "Sign in to Studio" }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Wavia Studio" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue securely" })).toBeVisible();
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-sign-in-desktop-20261107.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-sign-in-mobile-390-20261107.png"), fullPage: true });
  }
});

test("selects between two durable Wavia memberships and keeps tokens server-only", async ({ context, page }) => {
  await authenticate(context, "user-two");
  await page.goto("/workspaces");
  await expect(page.getByRole("button", { name: /Alpha workspace/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Beta workspace/ })).toBeVisible();
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-workspaces-desktop-20261107.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-workspaces-mobile-390-20261107.png"), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 720 });
  }

  await page.getByRole("button", { name: /Beta workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("link", { name: "Build" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Connect" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);

  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  const cookies = await context.cookies();
  expect(cookies.find((cookie) => cookie.name === "wos-session")?.httpOnly).toBe(true);
  expect(cookies.find((cookie) => cookie.name === "wavia-workspace")?.httpOnly).toBe(true);
});

test("rejects a forged selected-workspace cookie", async ({ context, page }) => {
  await authenticate(context, "user-two");
  await context.addCookies([{ name: "wavia-workspace", value: "v1.forged.signature", domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/workspaces$/);
});

test("shows an explicit no-membership state", async ({ context, page }) => {
  await authenticate(context, "user-none");
  await page.goto("/workspaces");
  await expect(page.getByRole("heading", { name: "No workspace access yet" })).toBeVisible();
});

test("rejects an expired WorkOS session", async ({ context, page }) => {
  await authenticate(context, "user-two", true);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/user_management\/authorize/);
  const cookies = await context.cookies();
  expect(cookies.some((cookie) => cookie.name === "wos-session")).toBe(false);
});

test("sign-out clears both the WorkOS and selected-workspace cookies", async ({ context, page }) => {
  await authenticate(context, "user-two");
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  const cookies = await context.cookies();
  expect(cookies.some((cookie) => cookie.name === "wos-session")).toBe(false);
  expect(cookies.some((cookie) => cookie.name === "wavia-workspace")).toBe(false);
});
