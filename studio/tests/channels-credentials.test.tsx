// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { pathname, requireWorkspace, loadAgents, getTelephonySettings } = vi.hoisted(() => ({
  pathname: { current: "/channels/web" },
  requireWorkspace: vi.fn(),
  loadAgents: vi.fn(),
  getTelephonySettings: vi.fn(),
}));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));
vi.mock("@/auth/workspace", async () => {
  const permissions = await import("@/auth/workspace-permissions");
  return { hasWorkspaceCapability: permissions.hasWorkspaceCapability, requireWorkspace };
});
vi.mock("@/features/agents/data", () => ({ loadAgents }));
vi.mock("@/features/channels/data", () => ({ getTelephonySettings }));
vi.mock("@/features/channels/actions", () => ({ saveTelephonyPolicyAction: vi.fn() }));
const { listAPIKeys, providerData } = vi.hoisted(() => ({
  listAPIKeys: vi.fn(),
  providerData: { getProviderCatalog: vi.fn(), listProviderCredentials: vi.fn(), getWorkspaceEntitlements: vi.fn() },
}));
vi.mock("@/features/api-keys/data", () => ({ listAPIKeys }));
vi.mock("@/features/api-keys/actions", () => ({ createAPIKeyAction: vi.fn(), revokeAPIKeyAction: vi.fn() }));
vi.mock("@/features/providers/data", () => providerData);
vi.mock("@/features/providers/actions", () => ({ storeProviderCredentialAction: vi.fn(), revokeProviderCredentialAction: vi.fn() }));

import TelephonyChannelPage from "@/app/(studio)/channels/telephony/page";
import APIKeysPage from "@/app/(studio)/developers/api-keys/page";
import ProvidersSettingsPage from "@/app/(studio)/settings/providers/page";
import WebChannelPage from "@/app/(studio)/channels/web/page";

import { WebChannelView } from "@/features/channels/web-channel-view";
import { TelephonyChannelView } from "@/features/channels/telephony-channel-view";
import { APIKeyManager } from "@/features/api-keys/api-key-manager";
import { ProviderCredentialManager } from "@/features/providers/provider-credential-manager";
import type { APIKeyDto, CatalogProviderDto, ProviderCredentialDto, TelephonySettingsDto } from "@/data/schema";

const sampleAgents = [
  { agent_id: "11111111-1111-4111-8111-111111111111", name: "Support Agent", is_published: true },
  { agent_id: "22222222-2222-4222-8222-222222222222", name: "Sales Agent", is_published: false },
];

const sampleKeys: APIKeyDto[] = [
  {
    key_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    name: "Production Web Client",
    key_prefix: "wavia_live_prod_abc",
    scopes: ["session:mint"],
    role: "tenant_viewer",
    created_at: "2026-10-01T00:00:00Z",
    expires_at: null,
    revoked_at: null,
    last_used_at: "2026-10-30T12:00:00Z",
  },
  {
    key_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    name: "Staging Test Key",
    key_prefix: "wavia_live_test_xyz",
    scopes: ["session:mint", "agent:read"],
    role: "tenant_editor",
    created_at: "2026-09-01T00:00:00Z",
    expires_at: "2026-10-01T00:00:00Z",
    revoked_at: "2026-09-15T00:00:00Z",
    last_used_at: null,
  },
];

const sampleCatalog: CatalogProviderDto[] = [
  { provider_id: "gladia", category: "stt", languages: ["en", "ur"], streaming_input: true, streaming_output: false, supports_tools: false, models: ["default"], readiness: "production" },
  { provider_id: "groq", category: "llm", languages: ["en"], streaming_input: false, streaming_output: true, supports_tools: true, models: ["llama-3.3-70b-versatile"], readiness: "production" },
  { provider_id: "cartesia", category: "tts", languages: ["en"], streaming_input: false, streaming_output: true, supports_tools: false, models: ["sonic-english"], readiness: "production" },
];

const sampleCredentials: ProviderCredentialDto[] = [
  {
    credential_id: "c111111111111111111111111111111111111111111111111111111111111111",
    provider_id: "groq",
    credential_type: "api_key",
    reference: "default",
    rotation_version: 1,
    status: "active",
    created_at: "2026-10-10T00:00:00Z",
    rotated_at: null,
  },
];

const sampleTelephony: TelephonySettingsDto = {
  policy: {
    outbound_enabled: false,
    allowed_destinations: ["+14155550100"],
    calling_timezone: "UTC",
    window_start: "09:00:00",
    window_end: "17:00:00",
    max_concurrent_calls: 1,
    max_calls_per_minute: 1,
    daily_spend_cap_cents: 100,
    reserved_spend_cents_per_call: 1,
    max_call_duration_seconds: 600,
  },
  readiness: {
    state: "not_configured",
    trunk_configured: false,
    telephony_entitled: false,
    carrier_health: "unknown",
  },
  carrier_actions_allowed: false,
};

afterEach(cleanup);

describe("WebChannelView", () => {
  it("renders embed snippet derived from @ucve/voice-sdk and updates on agent selection", () => {
    render(<WebChannelView agents={sampleAgents} defaultAgentId="11111111-1111-4111-8111-111111111111" />);
    expect(screen.getByText(/npm install @ucve\/voice-sdk/i)).toBeInTheDocument();
    const snippet = screen.getByTestId("embed-code-snippet");
    expect(snippet).toHaveTextContent("11111111-1111-4111-8111-111111111111");

    const select = screen.getByLabelText(/select agent/i);
    fireEvent.change(select, { target: { value: "22222222-2222-4222-8222-222222222222" } });
    expect(snippet).toHaveTextContent("22222222-2222-4222-8222-222222222222");
  });

  it("never exposes secret tokens or hardcoded private keys in generated snippets", () => {
    render(<WebChannelView agents={sampleAgents} defaultAgentId="11111111-1111-4111-8111-111111111111" />);
    const code = screen.getByTestId("embed-code-snippet").textContent ?? "";
    expect(code).not.toContain("wavia_live_");
    expect(code).not.toContain("eyJ");
    expect(code).toContain("YOUR_SERVER_MINT_ENDPOINT");
  });

  it("uses the SDK's exported UCVEVoiceClient contract", () => {
    render(<WebChannelView agents={sampleAgents} defaultAgentId="11111111-1111-4111-8111-111111111111" />);
    const code = screen.getByTestId("embed-code-snippet").textContent ?? "";
    expect(code).toContain('import { UCVEVoiceClient } from "@ucve/voice-sdk"');
    expect(code).toContain("new UCVEVoiceClient(token, {");
    expect(code).toContain("wsUrl: ws_url");
    expect(code).not.toContain("new VoiceClient");
  });
});

describe("TelephonyChannelView", () => {
  it("displays honest readiness without fake carrier actions", () => {
    render(<TelephonyChannelView settings={sampleTelephony} canEdit={true} onSave={vi.fn()} />);
    expect(screen.getByText(/Not configured/i)).toBeInTheDocument();
    expect(screen.getByText(/Carrier purchase and provisioning is not automated in self-serve mode/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /purchase phone number/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start campaign/i })).not.toBeInTheDocument();
  });

  it("disables editing and hides save button when user lacks telephony:write", () => {
    render(<TelephonyChannelView settings={sampleTelephony} canEdit={false} onSave={vi.fn()} />);
    expect(screen.getByLabelText(/allow outbound calls/i)).toBeDisabled();
    expect(screen.queryByRole("button", { name: /save policy/i })).not.toBeInTheDocument();
  });

  it("allows editing and submitting policy when canEdit is true", async () => {
    const onSave = vi.fn().mockResolvedValue({ success: true });
    render(<TelephonyChannelView settings={sampleTelephony} canEdit={true} onSave={onSave} />);
    const outboundCheckbox = screen.getByLabelText(/allow outbound calls/i);
    expect(outboundCheckbox).not.toBeDisabled();
    fireEvent.click(outboundCheckbox);

    const saveBtn = screen.getByRole("button", { name: /save policy/i });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ outbound_enabled: true })));
  });
});

describe("channel surfaces", () => {
  const workspace = (capabilities: string[]) => ({ session: { accessToken: "offline" }, membership: { tenant_id: "33333333-3333-4333-8333-333333333333", capabilities } });

  it("uses the shared header and channel tabs on the web page", async () => {
    pathname.current = "/channels/web";
    requireWorkspace.mockResolvedValue(workspace(["agent:read", "telephony:read"]));
    loadAgents.mockResolvedValue([{ agent_id: sampleAgents[0].agent_id, name: "Support Agent", is_published: true }]);

    const { container } = render(await WebChannelPage());

    expect(screen.getByRole("heading", { level: 1, name: "Channels" })).toBeVisible();
    const tabs = screen.getByRole("navigation", { name: "Channels" });
    expect(within(tabs).getByRole("link", { name: "Web" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "Telephony" })).toHaveAttribute("href", "/channels/telephony");
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
  });

  it("uses the shared header and channel tabs on the telephony page", async () => {
    pathname.current = "/channels/telephony";
    requireWorkspace.mockResolvedValue(workspace(["telephony:read"]));
    getTelephonySettings.mockResolvedValue(sampleTelephony);

    const { container } = render(await TelephonyChannelPage());

    expect(requireWorkspace).toHaveBeenCalledWith("telephony:read");
    expect(screen.getByRole("heading", { level: 1, name: "Channels" })).toBeVisible();
    expect(within(screen.getByRole("navigation", { name: "Channels" })).getByRole("link", { name: "Telephony" })).toHaveAttribute("aria-current", "page");
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    expect(screen.getByText("Your role can review telephony readiness and policy but cannot change them.")).toBeVisible();
  });

  it("warns that a draft agent cannot start sessions and handles a workspace with no agents", () => {
    const { container } = render(<WebChannelView agents={sampleAgents} defaultAgentId="22222222-2222-4222-8222-222222222222" />);
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Web voice integration" })).toBeVisible();
    expect(screen.getByText("Sales Agent is a draft. Sessions start only for published agents, so publish it before going live.")).toBeVisible();

    cleanup();
    render(<WebChannelView agents={[]} />);
    expect(screen.getByText("No agents yet. Create and publish an agent, then return here for its integration snippet.")).toBeVisible();
  });

  it("shows readiness as labelled badges and reports save outcomes with live roles", async () => {
    const onSave = vi.fn().mockResolvedValueOnce({ success: true }).mockResolvedValueOnce({ success: false, error: "Destinations must be E.164 numbers." });
    const { container } = render(<TelephonyChannelView settings={sampleTelephony} canEdit onSave={onSave} />);

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Telephony voice channel" })).toBeVisible();
    const readiness = screen.getByRole("region", { name: "Trunk readiness" });
    for (const text of ["Not configured", "Unconfigured", "Disabled", "unknown"]) {
      expect(within(readiness).getByText(text)).toBeVisible();
    }
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Telephony policy saved successfully.");
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Destinations must be E.164 numbers.");
  });
});

describe("APIKeyManager", () => {
  it("renders key list with prefix and status", () => {
    render(<APIKeyManager keys={sampleKeys} canManage={true} onCreate={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.getByText("Production Web Client")).toBeInTheDocument();
    expect(screen.getByText("wavia_live_prod_abc...")).toBeInTheDocument();
    expect(screen.getByText("Staging Test Key")).toBeInTheDocument();
    expect(screen.getByText("Revoked")).toBeInTheDocument();
  });

  it("hides create and revoke buttons when canManage is false (viewer role)", () => {
    render(<APIKeyManager keys={sampleKeys} canManage={false} onCreate={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /create api key/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revoke/i })).not.toBeInTheDocument();
  });

  it("enforces one-time key reveal with mandatory confirmation checkbox", async () => {
    const onCreate = vi.fn().mockResolvedValue({
      api_key: "wavia_live_new_secret_12345",
      key: {
        key_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        name: "New Integration",
        key_prefix: "wavia_live_new_",
        scopes: ["session:mint"],
        role: "tenant_viewer",
        created_at: "2026-10-31T00:00:00Z",
        expires_at: null,
        revoked_at: null,
        last_used_at: null,
      },
    });

    render(<APIKeyManager keys={sampleKeys} canManage={true} onCreate={onCreate} onRevoke={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /create api key/i }));

    fireEvent.change(screen.getByLabelText(/key name/i), { target: { value: "New Integration" } });
    fireEvent.click(screen.getByRole("button", { name: /generate key/i }));

    await waitFor(() => expect(screen.getByText("wavia_live_new_secret_12345")).toBeInTheDocument());
    expect(screen.getByText(/save this secret key now/i)).toBeInTheDocument();

    const closeBtn = screen.getByRole("button", { name: /done/i });
    expect(closeBtn).toBeDisabled();

    const ackCheckbox = screen.getByLabelText(/i have copied this secret key/i);
    fireEvent.click(ackCheckbox);
    expect(closeBtn).not.toBeDisabled();

    fireEvent.click(closeBtn);
    expect(screen.queryByText("wavia_live_new_secret_12345")).not.toBeInTheDocument();
  });

  it("copies the one-time secret without writing browser storage", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    localStorage.clear();
    sessionStorage.clear();
    const onCreate = vi.fn().mockResolvedValue({
      api_key: "wavia_live_copy_only_secret",
      key: { ...sampleKeys[0], key_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd" },
    });
    render(<APIKeyManager keys={sampleKeys} canManage={true} onCreate={onCreate} onRevoke={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /create api key/i }));
    fireEvent.change(screen.getByLabelText(/key name/i), { target: { value: "Clipboard test" } });
    fireEvent.click(screen.getByRole("button", { name: /generate key/i }));
    await screen.findByText("wavia_live_copy_only_secret");
    fireEvent.click(screen.getByRole("button", { name: /copy to clipboard/i }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("wavia_live_copy_only_secret"));
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("requires confirmation before revoking an API key", async () => {
    const onRevoke = vi.fn().mockResolvedValue({ success: true });
    render(<APIKeyManager keys={sampleKeys} canManage={true} onCreate={vi.fn()} onRevoke={onRevoke} />);

    const revokeButtons = screen.getAllByRole("button", { name: /revoke/i });
    fireEvent.click(revokeButtons[0]);

    expect(screen.getByText(/are you sure you want to revoke/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole("button", { name: /confirm revoke/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(onRevoke).toHaveBeenCalledWith("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"));
  });

  it("keeps the revoke confirmation open when revocation fails", async () => {
    const onRevoke = vi.fn().mockResolvedValue({ success: false, error: "Revocation failed safely." });
    render(<APIKeyManager keys={sampleKeys} canManage={true} onCreate={vi.fn()} onRevoke={onRevoke} />);
    fireEvent.click(screen.getAllByRole("button", { name: /revoke/i })[0]);
    fireEvent.click(screen.getByRole("button", { name: /confirm revoke/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Revocation failed safely.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("ProviderCredentialManager", () => {
  it("renders catalog providers and indicates configuration status", () => {
    render(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={false} canManage={true} onSave={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.getByText(/groq/i)).toBeInTheDocument();
    expect(screen.getByText(/^Configured$/)).toBeInTheDocument();
    expect(screen.getByText(/gladia/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^Not configured$/)).toHaveLength(2);
  });

  it("redacts secret input as type=password and never echoes existing secret", async () => {
    render(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={false} canManage={true} onSave={vi.fn()} onRevoke={vi.fn()} />);
    const configureBtn = screen.getByRole("button", { name: /configure groq/i });
    fireEvent.click(configureBtn);

    const secretInput = screen.getByLabelText(/api key or secret/i) as HTMLInputElement;
    expect(secretInput.type).toBe("password");
    expect(secretInput.value).toBe("");
  });

  it("hides configure and revoke buttons when canManage is false (viewer role)", () => {
    render(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={false} canManage={false} onSave={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /configure/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revoke/i })).not.toBeInTheDocument();
  });

  it("displays advanced routing notice based on entitlement", () => {
    const { rerender } = render(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={false} canManage={true} onSave={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.getByText(/Standard release chain active/i)).toBeInTheDocument();

    rerender(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={true} canManage={true} onSave={vi.fn()} onRevoke={vi.fn()} />);
    expect(screen.getByText(/Advanced provider routing enabled/i)).toBeInTheDocument();
  });

  it("keeps the credential revoke confirmation open when revocation fails", async () => {
    const onRevoke = vi.fn().mockResolvedValue({ success: false, error: "Credential remains active." });
    render(<ProviderCredentialManager catalog={sampleCatalog} credentials={sampleCredentials} advancedEnabled={false} canManage={true} onSave={vi.fn()} onRevoke={onRevoke} />);
    fireEvent.click(screen.getByRole("button", { name: /^revoke$/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm revoke/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Credential remains active.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("developer surfaces", () => {
  const workspace = (capabilities: string[]) => ({ session: { accessToken: "offline" }, membership: { tenant_id: "33333333-3333-4333-8333-333333333333", capabilities } });

  it("composes the API keys page with a shared header and no inline styles", async () => {
    requireWorkspace.mockResolvedValue(workspace(["api_key:read", "api_key:write"]));
    listAPIKeys.mockResolvedValue(sampleKeys);

    const { container } = render(await APIKeysPage());

    expect(requireWorkspace).toHaveBeenCalledWith("api_key:read");
    expect(screen.getByRole("heading", { level: 1, name: "API keys" })).toBeVisible();
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    const table = screen.getByRole("table", { name: "API keys" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Production Web Client");
    expect(within(rows[1]).getByText("Active")).toBeVisible();
    expect(within(rows[2]).getByText("Revoked")).toBeVisible();
    expect(within(rows[1]).getByText("1 Oct 2026")).toBeVisible();
  });

  it("opens a labelled create dialog that focuses the name field and closes on Escape", () => {
    render(<APIKeyManager keys={sampleKeys} canManage onCreate={vi.fn()} onRevoke={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create API key" }));

    const dialog = screen.getByRole("dialog", { name: "Create API key" });
    expect(within(dialog).getByLabelText("Key name")).toHaveFocus();
    expect(within(dialog).getAllByRole("radio")).toHaveLength(2);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does not let Escape dismiss an unacknowledged one-time secret", async () => {
    const onCreate = vi.fn().mockResolvedValue({ api_key: "wavia_live_escape_secret_1", key: { ...sampleKeys[0], key_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee" } });
    render(<APIKeyManager keys={sampleKeys} canManage onCreate={onCreate} onRevoke={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create API key" }));
    fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "Escape test" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate key" }));

    const reveal = await screen.findByRole("dialog", { name: "Save this secret key now" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(reveal).toBeInTheDocument();
    expect(within(reveal).getByText("wavia_live_escape_secret_1")).toBeVisible();
  });

  it("revokes a key through the shared confirmation dialog", () => {
    render(<APIKeyManager keys={sampleKeys} canManage onCreate={vi.fn()} onRevoke={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Revoke Production Web Client" }));

    const dialog = screen.getByRole("dialog", { name: "Revoke API key" });
    expect(dialog).toHaveTextContent("Production Web Client");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("composes provider credentials with readable provider names and shared dialogs", async () => {
    requireWorkspace.mockResolvedValue(workspace(["provider_credential:read", "provider_credential:write"]));
    providerData.getProviderCatalog.mockResolvedValue(sampleCatalog);
    providerData.listProviderCredentials.mockResolvedValue(sampleCredentials);
    providerData.getWorkspaceEntitlements.mockResolvedValue({ advanced_providers_enabled: false });

    const { container } = render(await ProvidersSettingsPage());

    expect(requireWorkspace).toHaveBeenCalledWith("provider_credential:read");
    expect(screen.getByRole("heading", { level: 1, name: "AI provider credentials" })).toBeVisible();
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    for (const stage of ["Speech-to-text (STT)", "Language models (LLM)", "Text-to-speech (TTS)"]) {
      expect(screen.getByRole("table", { name: stage })).toBeVisible();
    }
    expect(screen.getByRole("cell", { name: "Groq" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Configure groq" }));
    const configure = screen.getByRole("dialog", { name: "Configure Groq" });
    expect(within(configure).getByLabelText("API key or secret")).toHaveFocus();
    fireEvent.click(within(configure).getByRole("button", { name: "Cancel" }));

    fireEvent.click(screen.getByRole("button", { name: /^revoke$/i }));
    expect(screen.getByRole("dialog", { name: "Revoke credential" })).toHaveTextContent("Groq");
  });
});
