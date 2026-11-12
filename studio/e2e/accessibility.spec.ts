import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

const CUSTOMER_ROUTES = [
  "/dashboard",
  "/onboarding",
  "/agents",
  "/agents/new",
  "/test",
  "/knowledge",
  "/channels/web",
  "/channels/telephony",
  "/conversations",
  "/conversations/91111111-1111-4111-8111-111111111111",
  "/developers/api-keys",
  "/settings",
  "/settings/members",
  "/settings/providers",
  "/settings/usage",
  "/settings/audit",
];
const ADMIN_ROUTES = [
  "/admin",
  "/admin/tenants",
  "/admin/tenants/11111111-1111-4111-8111-111111111111",
  "/admin/support-sessions",
  "/admin/operations",
  "/admin/staff",
  "/admin/audit",
];

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

async function seriousViolations(page: Page) {
  const result = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return result.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => ({ id: violation.id, targets: violation.nodes.map((node) => node.target.join(" ")).slice(0, 5) }));
}

async function noHorizontalOverflow(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
}

async function customerSession(context: BrowserContext, page: Page) {
  await authenticate(context, "user-two");
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test.beforeEach(async () => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
});

test("customer routes have no serious or critical WCAG 2.1 AA violations", async ({ context, page }) => {
  await customerSession(context, page);
  const findings: Record<string, unknown> = {};
  for (const path of CUSTOMER_ROUTES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const violations = await seriousViolations(page);
    if (violations.length) findings[path] = violations;
  }
  expect(findings).toEqual({});
});

test("internal routes have no serious or critical WCAG 2.1 AA violations", async ({ context, page }) => {
  await authenticate(context, "user-platform-admin");
  const findings: Record<string, unknown> = {};
  for (const path of ADMIN_ROUTES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const violations = await seriousViolations(page);
    if (violations.length) findings[path] = violations;
  }
  // Dialogs are part of the surface too.
  await page.goto("/admin/staff");
  await page.getByRole("button", { name: "Grant a role" }).click();
  const dialogViolations = await seriousViolations(page);
  if (dialogViolations.length) findings["/admin/staff (grant dialog)"] = dialogViolations;

  // An active support session page, with its read-only banner and data tables.
  await page.goto("/admin/tenants/22222222-2222-4222-8222-222222222222");
  await page.getByRole("button", { name: "Start support session" }).click();
  const start = page.getByRole("dialog", { name: "Start a support session" });
  await start.getByLabel("Reason").fill("Accessibility review of support view");
  await start.getByRole("checkbox", { name: /Readiness/ }).check();
  const startViolations = await seriousViolations(page);
  if (startViolations.length) findings["/admin/tenants/[id] (start dialog)"] = startViolations;
  await start.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByRole("region", { name: "Support session" })).toBeVisible();
  const sessionViolations = await seriousViolations(page);
  if (sessionViolations.length) findings["/admin/support-sessions/[id]"] = sessionViolations;
  expect(findings).toEqual({});
});

test("every customer and internal route fits a 320px viewport", async ({ browser }) => {
  const overflow: string[] = [];
  const customer = await browser.newContext({ viewport: { width: 320, height: 700 } });
  const customerPage = await customer.newPage();
  await customerSession(customer, customerPage);
  for (const path of CUSTOMER_ROUTES) {
    await customerPage.goto(path);
    await expect(customerPage.getByRole("heading", { level: 1 })).toBeVisible();
    if (!(await noHorizontalOverflow(customerPage))) overflow.push(path);
  }
  await customer.close();

  const staff = await browser.newContext({ viewport: { width: 320, height: 700 } });
  await authenticate(staff, "user-platform-admin");
  const staffPage = await staff.newPage();
  for (const path of ADMIN_ROUTES) {
    await staffPage.goto(path);
    await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();
    if (!(await noHorizontalOverflow(staffPage))) overflow.push(path);
  }
  await staff.close();
  expect(overflow).toEqual([]);
});

test("reduced motion removes transitions and animations", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await customerSession(context, page);
  await page.goto("/settings");
  const durations = await page.evaluate(() => {
    const sidebar = document.querySelector(".studio-sidebar");
    // Inspect the loading mark's animation without waiting for a real loading state.
    const probe = document.createElement("section");
    probe.className = "state-card state-card--loading";
    probe.innerHTML = '<span class="state-card__mark"></span>';
    document.body.appendChild(probe);
    const mark = probe.querySelector(".state-card__mark") as HTMLElement;
    const result = {
      sidebarTransition: sidebar ? getComputedStyle(sidebar).transitionDuration : "missing",
      loadingAnimation: getComputedStyle(mark).animationDuration,
      loadingIterations: getComputedStyle(mark).animationIterationCount,
    };
    probe.remove();
    return result;
  });
  expect(durations.sidebarTransition.split(",").every((value) => parseFloat(value) <= 0.001)).toBe(true);
  expect(parseFloat(durations.loadingAnimation)).toBeLessThanOrEqual(0.001);
  expect(durations.loadingIterations).toBe("1");
  await context.close();
});
