import { expect, test, type Page } from "@playwright/test";

/**
 * Stage 3 customer journey against the real control plane, worker and
 * database (see playwright.journey.config.ts). Every step must complete for
 * real: a page that only renders is not a pass.
 */
const runId = Date.now().toString(36);
const email = `owner-${runId}@journey.test`;
const workspaceName = `Journey ${runId}`;

async function signUp(page: Page) {
  await page.goto("/sign-up");
  await page.getByRole("button", { name: "Create an account" }).click();
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/workspaces/);
}

test.describe.serial("self-serve customer journey (real engine)", () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    page.on("pageerror", (error) => console.log(`[pageerror] ${error.message}`));
  });

  test("signs up through hosted sign-in and creates a workspace", async () => {
    await signUp(page);
    await expect(page.getByRole("heading", { name: "No workspace access yet" })).toBeVisible();
    await page.getByLabel("Workspace name").fill(workspaceName);
    await page.getByRole("button", { name: "Create workspace" }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
  });

  test("completes onboarding", async () => {
    await expect(page.getByRole("heading").first()).toBeVisible();
    const business = page.getByLabel("Business name");
    if (await business.inputValue() === "") await business.fill(workspaceName);
    await page.getByLabel("Primary use case").selectOption("appointments");
    await page.getByLabel("Operating region").fill("United Arab Emirates");
    await page.getByRole("button", { name: "Save and continue" }).click();
    await expect(page.getByText("Onboarding saved.")).toBeVisible();
    await page.goto("/dashboard");
    await expect(page.getByText("1 item remaining")).toHaveCount(0);
  });

  test("creates, configures and publishes an agent", async () => {
    await page.getByRole("link", { name: "Build", exact: true }).click();
    await expect(page).toHaveURL(/\/agents$/);
    await page.getByRole("link", { name: "Create agent" }).first().click();
    await expect(page.getByRole("heading", { name: "Create an agent" })).toBeVisible();
    await page.locator("label.choice-card").first().click();
    await page.getByLabel("Agent name").fill("Front desk");
    await page.getByRole("button", { name: "Create agent" }).click();
    await page.getByRole("link", { name: "Continue building" }).click();
    await page.getByLabel("Description").fill("Answers opening hours and books appointments");
    await expect(page.getByText(/Saved at revision/)).toBeVisible();
    await page.getByRole("button", { name: "Check readiness" }).click();
    await expect(page.getByText("Ready to publish.")).toBeVisible();
    await page.getByRole("button", { name: "Publish agent" }).click();
    await expect(page.getByText(/Published version 1/)).toBeVisible();
  });

  test("runs a real browser voice test against the worker", async () => {
    await page.getByRole("link", { name: "Test", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Test an agent" })).toBeVisible();
    await page.getByRole("link", { name: "Open Front desk test sandbox" }).click();
    await expect(page.getByRole("heading", { name: "Browser voice test" })).toBeVisible();
    await page.getByRole("button", { name: "Start voice test" }).click();
    await expect(page.getByText("What are your opening hours?").first()).toBeVisible({ timeout: 60_000 });
    // The worker's real VAD ended the caller's turn; the agent's (mock
    // provider) reply streamed back over the same session.
    await expect(page.getByText(/Mock reply to: What are your opening hours\?/).first()).toBeVisible({ timeout: 60_000 });
    // Canonical turn latency (end of speech -> first audible sample) arrives
    // from the worker once playback is acknowledged.
    await expect(page.locator("dt", { hasText: "Audible end to end" }).locator("+ dd")).not.toHaveText("Not measured", { timeout: 30_000 });
    await page.getByRole("button", { name: "End test" }).click();
    await expect(page.getByText("Connection:").locator("..")).toContainText("disconnected");
  });

  test("sees the call in conversations and usage", async () => {
    await page.goto("/conversations");
    await expect.poll(async () => {
      await page.reload();
      return page.getByRole("row").count();
    }, { timeout: 60_000, intervals: [3_000] }).toBeGreaterThan(1);
    const shots = "../hamza_local/stage3/screens";
    await page.screenshot({ path: `${shots}/conversations.png`, fullPage: true });
    await page.getByRole("row").nth(1).getByRole("link").first().click();
    await expect(page.getByText("What are your opening hours?").first()).toBeVisible();
    // The jobs runner processes the post-call queue (mock provider mode: the
    // labelled mock provider, quoting the real transcript).
    await expect.poll(async () => {
      await page.reload();
      return page.getByText(/Mock summary \(no model was called\)/).count();
    }, { timeout: 90_000, intervals: [3_000] }).toBeGreaterThan(0);
    await page.screenshot({ path: `${shots}/conversation-detail.png`, fullPage: true });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await page.screenshot({ path: `${shots}/dashboard.png`, fullPage: true });
    await page.goto("/settings");
    await page.screenshot({ path: `${shots}/settings.png`, fullPage: true });
  });

  test("developer creates an API key and the SDK quickstart runs with it", async () => {
    await page.goto("/developers/api-keys");
    await page.getByRole("button", { name: "Create API Key" }).click();
    await page.getByLabel("Key Name").fill("Journey backend");
    await page.getByRole("button", { name: "Generate Key" }).click();
    await expect(page.getByText("Save this secret key now")).toBeVisible();
    const secret = (await page.getByRole("dialog").locator("pre.secret-value").textContent())?.trim() ?? "";
    expect(secret).toMatch(/^ucve_live_/);
    await page.getByLabel("I have copied this secret key").check();
    await page.getByRole("button", { name: "Done" }).click();
    await page.reload();
    await expect(page.getByText(secret)).toHaveCount(0);

    const agentId = (await page.locator(".integration-details__agents dd").first().textContent())?.trim() ?? "";
    expect(agentId).toMatch(/^[0-9a-f-]{36}$/);
    await expect(page.locator(".integration-details__snippet")).toContainText(agentId);

    // An outside developer: SDK from source, the key and agent ID only.
    const { spawnSync } = await import("node:child_process");
    const python = process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";
    const run = spawnSync(python, [
      "../sdk/python/examples/quickstart.py",
      "--control-plane", "http://127.0.0.1:28080",
      "--agent", agentId,
      "--timeout", "30",
    ], { encoding: "utf8", env: { ...process.env, PYTHONPATH: "../sdk/python", WAVIA_API_KEY: secret }, timeout: 90_000 });
    expect(run.status, `${run.stdout}\n${run.stderr}`).toBe(0);
    expect(run.stdout).toMatch(/received \d+ bytes of agent audio/);

    await page.goto("/settings/usage");
    await page.screenshot({ path: "../hamza_local/stage3/screens/usage.png", fullPage: true });
  });

  test("adds knowledge, waits for real ingestion, activates and connects it", async () => {
    await page.getByRole("link", { name: "Knowledge", exact: true }).click();
    await page.getByLabel("Knowledge base name").fill("Clinic handbook");
    await page.getByRole("button", { name: "Create knowledge base" }).click();
    await expect(page.getByRole("heading", { name: "Clinic handbook" })).toBeVisible();
    await page.getByLabel("FAQ name").fill("Opening hours");
    await page.getByLabel("Question", { exact: true }).fill("When are you open?");
    await page.getByLabel("Answer", { exact: true }).fill("We are open from 9 AM to 6 PM, Sunday to Thursday.");
    await page.getByRole("button", { name: "Add FAQ" }).click();
    await expect(page.getByText("Opening hours.json", { exact: true })).toBeVisible();
    // The jobs runner embeds sources; poll until the engine reports Ready.
    await expect.poll(async () => {
      await page.reload();
      return page.getByRole("listitem", { name: "Opening hours.json" }).getByText("Ready").count();
    }, { timeout: 120_000, intervals: [3_000] }).toBe(1);
    await page.getByLabel("Ask your knowledge").fill("When are you open?");
    await page.getByRole("button", { name: "Preview answer" }).click();
    await expect(page.getByText(/9 AM to 6 PM/).first()).toBeVisible();
    await page.getByRole("button", { name: "Activate knowledge" }).click();
    await expect(page.getByText(/Knowledge revision 1 is active/)).toBeVisible();
    await page.getByRole("button", { name: "Connect to agent" }).click();
    await expect(page.getByText(/Connected to Front desk/)).toBeVisible();
  });
});
