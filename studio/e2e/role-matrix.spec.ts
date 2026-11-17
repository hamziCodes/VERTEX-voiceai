import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const FORBIDDEN_MESSAGE = "You do not have permission to open that area.";

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

async function selectWorkspace(page: Page, name: RegExp) {
  await page.goto("/workspaces");
  await page.getByRole("button", { name }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function navigationLabels(page: Page, name: string): Promise<string[]> {
  // The visible label only; the glyph and screen-reader prefix are separate spans.
  return page.getByRole("navigation", { name }).locator(".studio-nav-link__label").allInnerTexts();
}

// Customer roles: exact navigation and every route their capabilities do not cover.
const CUSTOMER_ROLES: ReadonlyArray<{ subject: string; role: string; navigation: string[]; allowed: string[]; forbidden: string[] }> = [
  {
    subject: "user-two",
    role: "tenant_admin",
    navigation: ["Setup", "Build", "Knowledge", "Test", "Connect", "Conversations", "API keys", "Webhooks", "Providers", "Settings"],
    allowed: ["/agents", "/knowledge", "/channels/telephony", "/developers/api-keys", "/settings/providers", "/settings/members", "/settings/audit"],
    forbidden: [],
  },
  {
    subject: "user-editor",
    role: "tenant_editor",
    navigation: ["Setup", "Build", "Knowledge", "Test", "Connect", "Conversations", "Settings"],
    allowed: ["/agents", "/knowledge", "/conversations", "/settings/members", "/settings/audit"],
    forbidden: ["/developers/api-keys", "/developers/webhooks", "/settings/providers"],
  },
  {
    subject: "user-developer",
    role: "tenant_developer",
    navigation: ["Build", "Test", "Connect", "API keys", "Webhooks", "Providers"],
    allowed: ["/agents", "/test", "/developers/api-keys", "/developers/webhooks", "/settings/providers", "/settings/usage"],
    forbidden: ["/knowledge", "/onboarding", "/conversations", "/settings/audit", "/settings/members"],
  },
  {
    subject: "user-viewer",
    role: "tenant_viewer",
    navigation: ["Setup", "Build", "Knowledge", "Test", "Conversations"],
    allowed: ["/agents", "/knowledge", "/conversations", "/settings/usage"],
    forbidden: ["/developers/api-keys", "/settings/providers", "/settings/audit", "/settings/members", "/channels/telephony"],
  },
  {
    subject: "user-compliance",
    role: "compliance_admin",
    navigation: ["Conversations"],
    allowed: ["/conversations", "/settings/audit"],
    forbidden: ["/agents", "/knowledge", "/test", "/developers/api-keys", "/settings/usage", "/settings/members"],
  },
];

test.beforeEach(async () => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
});

for (const entry of CUSTOMER_ROLES) {
  test(`${entry.role} sees only its navigation and is refused every other route`, async ({ context, page }) => {
    await authenticate(context, entry.subject);
    await selectWorkspace(page, /Alpha workspace/);
    expect(await navigationLabels(page, "Workspace")).toEqual(entry.navigation);
    await expect(page.getByRole("navigation", { name: "Wavia admin" })).toHaveCount(0);

    for (const path of entry.allowed) {
      await page.goto(path);
      await expect(page, path).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
    for (const path of entry.forbidden) {
      await page.goto(path);
      await expect(page, path).toHaveURL(/\/workspaces\?error=forbidden$/);
      await expect(page.getByRole("alert").filter({ hasText: FORBIDDEN_MESSAGE })).toBeVisible();
    }
    for (const path of ["/admin", "/admin/support-sessions", "/admin/operations"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    }
  });
}

test("a member's role is per workspace: the same person is read-only elsewhere", async ({ context, page }) => {
  await authenticate(context, "user-editor");
  await selectWorkspace(page, /Beta workspace/);
  expect(await navigationLabels(page, "Workspace")).toEqual(["Setup", "Build", "Knowledge", "Test", "Conversations"]);
  await page.goto("/settings/members");
  await expect(page).toHaveURL(/\/workspaces\?error=forbidden$/);
});

const PLATFORM_ROLES: ReadonlyArray<{ subject: string; navigation: string[]; allowed: string[]; forbidden: string[] }> = [
  {
    subject: "user-platform-support",
    navigation: ["Overview", "Tenants", "Support sessions"],
    allowed: ["/admin", "/admin/tenants", "/admin/support-sessions"],
    forbidden: ["/admin/operations", "/admin/staff", "/admin/audit"],
  },
  {
    subject: "user-platform-admin",
    navigation: ["Overview", "Tenants", "Support sessions", "Operations", "Staff", "Audit"],
    allowed: ["/admin", "/admin/tenants", "/admin/support-sessions", "/admin/operations", "/admin/staff", "/admin/audit"],
    forbidden: [],
  },
];

for (const entry of PLATFORM_ROLES) {
  test(`${entry.subject} sees only its internal navigation and has no customer workspace`, async ({ context, page }) => {
    await authenticate(context, entry.subject);
    await page.goto("/admin");
    expect(await navigationLabels(page, "Wavia admin")).toEqual(entry.navigation);
    for (const path of entry.allowed) {
      await page.goto(path);
      await expect(page, path).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    }
    for (const path of entry.forbidden) {
      await page.goto(path);
      await expect(page, path).toHaveURL(/\/admin\?error=forbidden$/);
    }
    // Staff without memberships cannot enter a customer workspace.
    await page.goto("/workspaces");
    await expect(page.getByRole("heading", { name: "No workspace access yet" })).toBeVisible();
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/workspaces$/);
  });
}
