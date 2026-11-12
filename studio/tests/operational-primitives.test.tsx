// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { pathname } = vi.hoisted(() => ({ pathname: { current: "/settings/usage" } }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

import AgentTestError from "@/app/(studio)/agents/[agentId]/test/error";
import AgentTestLoading from "@/app/(studio)/agents/[agentId]/test/loading";
import TelephonyError from "@/app/(studio)/channels/telephony/error";
import TelephonyLoading from "@/app/(studio)/channels/telephony/loading";
import WebChannelError from "@/app/(studio)/channels/web/error";
import WebChannelLoading from "@/app/(studio)/channels/web/loading";
import ConversationDetailError from "@/app/(studio)/conversations/[callId]/error";
import ConversationDetailLoading from "@/app/(studio)/conversations/[callId]/loading";
import ConversationsError from "@/app/(studio)/conversations/error";
import ConversationsLoading from "@/app/(studio)/conversations/loading";
import ApiKeysError from "@/app/(studio)/developers/api-keys/error";
import ApiKeysLoading from "@/app/(studio)/developers/api-keys/loading";
import KnowledgeError from "@/app/(studio)/knowledge/error";
import KnowledgeLoading from "@/app/(studio)/knowledge/loading";
import AuditError from "@/app/(studio)/settings/audit/error";
import AuditLoading from "@/app/(studio)/settings/audit/loading";
import ProvidersError from "@/app/(studio)/settings/providers/error";
import ProvidersLoading from "@/app/(studio)/settings/providers/loading";
import UsageError from "@/app/(studio)/settings/usage/error";
import UsageLoading from "@/app/(studio)/settings/usage/loading";
import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { RouteTabs } from "@/components/studio/route-tabs";
import { OperationsNavigation } from "@/features/operations/operations-navigation";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";

afterEach(() => {
  cleanup();
  pathname.current = "/settings/usage";
});

describe("route tabs", () => {
  it("marks only the current route and keeps a labelled navigation landmark", () => {
    pathname.current = "/channels/telephony";
    render(<RouteTabs items={[{ href: "/channels/web", label: "Web" }, { href: "/channels/telephony", label: "Telephony" }]} label="Channels" />);

    const nav = screen.getByRole("navigation", { name: "Channels" });
    expect(within(nav).getByRole("link", { name: "Telephony" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Web" })).not.toHaveAttribute("aria-current");
  });

  it("can match nested routes for list and detail pages", () => {
    pathname.current = "/conversations/11111111-1111-4111-8111-111111111111";
    render(<RouteTabs items={[{ href: "/conversations", label: "Conversations", matchNested: true }, { href: "/settings/usage", label: "Usage" }]} label="Operations" />);

    expect(screen.getByRole("link", { name: "Conversations" })).toHaveAttribute("aria-current", "page");
  });

  it("renders operations tabs filtered by server capabilities", () => {
    render(<OperationsNavigation capabilities={["conversation:read", "usage:read"]} />);

    const nav = screen.getByRole("navigation", { name: "Operations" });
    expect(within(nav).getByRole("link", { name: "Usage" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Conversations" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Audit" })).not.toBeInTheDocument();
  });
});

describe("confirm dialog", () => {
  function renderDialog(overrides: Partial<Parameters<typeof ConfirmDialog>[0]> = {}) {
    const props = {
      confirmLabel: "Revoke key",
      onCancel: vi.fn(),
      onConfirm: vi.fn(),
      title: "Revoke API key",
      children: <p>Services using this key lose access immediately.</p>,
      ...overrides,
    };
    const trigger = document.createElement("button");
    trigger.textContent = "Open";
    document.body.appendChild(trigger);
    trigger.focus();
    const view = render(<ConfirmDialog {...props} />);
    return { props, trigger, ...view };
  }

  it("is a labelled modal that focuses Cancel and closes on Escape", () => {
    const { props } = renderDialog();

    const dialog = screen.getByRole("dialog", { name: "Revoke API key" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Services using this key lose access immediately.");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("confirms explicitly, shows failures inside the dialog and ignores Escape while busy", () => {
    const { props, rerender } = renderDialog();

    fireEvent.click(screen.getByRole("button", { name: "Revoke key" }));
    expect(props.onConfirm).toHaveBeenCalledTimes(1);

    rerender(<ConfirmDialog {...props} busy error="The key could not be revoked." />);
    expect(within(screen.getByRole("dialog")).getByRole("alert")).toHaveTextContent("The key could not be revoked.");
    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(props.onCancel).not.toHaveBeenCalled();
  });

  it("returns focus to the control that opened it", () => {
    const { trigger, unmount } = renderDialog();

    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
});

describe("formatting", () => {
  it("formats timestamps the same way on server and browser", () => {
    expect(formatDateTime("2026-11-04T09:00:00Z")).toBe("4 Nov 2026, 09:00 UTC");
    expect(formatDateTime("2026-11-04T23:30:00+05:00")).toBe("4 Nov 2026, 18:30 UTC");
    expect(formatDate("2026-11-04T23:30:00Z")).toBe("4 Nov 2026");
    expect(formatDateTime("not a date")).toBe("Unknown time");
    expect(formatDate(null)).toBe("—");
  });

  it("groups numbers and keeps up to two decimals", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(12.5)).toBe("12.5");
    expect(formatNumber(0.126)).toBe("0.13");
  });
});

describe("route loading and error states", () => {
  const routes: Array<[string, ComponentType, ComponentType<{ reset: () => void }>]> = [
    ["knowledge", KnowledgeLoading, KnowledgeError],
    ["browser voice test", AgentTestLoading, AgentTestError],
    ["web channel", WebChannelLoading, WebChannelError],
    ["telephony channel", TelephonyLoading, TelephonyError],
    ["API keys", ApiKeysLoading, ApiKeysError],
    ["provider credentials", ProvidersLoading, ProvidersError],
    ["conversations", ConversationsLoading, ConversationsError],
    ["conversation detail", ConversationDetailLoading, ConversationDetailError],
    ["usage", UsageLoading, UsageError],
    ["audit", AuditLoading, AuditError],
  ];

  it.each(routes)("%s has a busy loading state and a retryable error that claims no change", (_name, Loading, ErrorState) => {
    const { unmount } = render(<Loading />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    unmount();

    const reset = vi.fn();
    render(<ErrorState reset={reset} />);
    const alert = screen.getByRole("alert");
    expect(alert).not.toHaveTextContent(/saved|success|updated|completed/i);
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
