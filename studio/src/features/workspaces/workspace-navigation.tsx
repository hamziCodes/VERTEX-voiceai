"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { hasWorkspaceCapability, type WorkspaceCapability, type WorkspaceRole } from "@/auth/workspace-permissions";

import {
  getSidebarPreferenceSnapshot,
  setSidebarPreference,
  subscribeSidebarPreference,
} from "./sidebar-preference";

type NavigationItem = {
  label: string;
  shortLabel: string;
  screenReaderPrefix?: string;
  href: string;
  permission: WorkspaceCapability;
  active(pathname: string): boolean;
};

type NavigationGroup = { label: string; items: ReadonlyArray<NavigationItem> };

const MOBILE_QUERY = "(max-width: 720px)";

function subscribeMobileViewport(onStoreChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => undefined;
  }
  const query = window.matchMedia(MOBILE_QUERY);
  query.addEventListener("change", onStoreChange);
  return () => query.removeEventListener("change", onStoreChange);
}

function getMobileViewportSnapshot(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(MOBILE_QUERY).matches
    : false;
}

const startsWith = (prefix: string) => (pathname: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);

const GROUPS: ReadonlyArray<NavigationGroup> = [
  {
    label: "Create",
    items: [
      { label: "Setup", shortLabel: "S", href: "/onboarding", permission: "onboarding:read", active: startsWith("/onboarding") },
      { label: "Build", shortLabel: "B", href: "/agents", permission: "agent:read", active: (path) => startsWith("/agents")(path) && !path.endsWith("/test") },
      { label: "Knowledge", shortLabel: "K", href: "/knowledge", permission: "knowledge:read", active: startsWith("/knowledge") },
      { label: "Test", shortLabel: "T", href: "/test", permission: "session:read", active: (path) => path === "/test" || (path.startsWith("/agents/") && path.endsWith("/test")) },
      { label: "Connect", shortLabel: "C", href: "/channels", permission: "telephony:read", active: startsWith("/channels") },
    ],
  },
  {
    label: "Operate",
    items: [
      { label: "Conversations", shortLabel: "O", screenReaderPrefix: "Operate", href: "/conversations", permission: "conversation:read", active: startsWith("/conversations") },
    ],
  },
  {
    label: "Developer",
    items: [
      { label: "API keys", shortLabel: "A", href: "/developers/api-keys", permission: "api_key:read", active: startsWith("/developers/api-keys") },
      { label: "Providers", shortLabel: "P", href: "/settings/providers", permission: "provider_credential:read", active: startsWith("/settings/providers") },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Settings", shortLabel: "W", href: "/settings", permission: "member:write", active: startsWith("/settings") },
    ],
  },
];

export function WorkspaceNavigation({
  capabilities,
  role,
  tenantName,
  displayName,
  signOutAction,
}: {
  capabilities: readonly string[];
  role: WorkspaceRole;
  tenantName?: string;
  displayName?: string;
  signOutAction?: () => Promise<void>;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const collapsed = useSyncExternalStore(
    subscribeSidebarPreference,
    getSidebarPreferenceSnapshot,
    () => false,
  );
  const isMobile = useSyncExternalStore(
    subscribeMobileViewport,
    getMobileViewportSnapshot,
    () => false,
  );
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setMobileOpen(false);
      mobileTriggerRef.current?.focus();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  const toggleCollapsed = () => {
    setSidebarPreference(!collapsed);
  };

  const toggleMobile = () => setMobileOpen((current) => !current);

  return (
    <>
      <button
        aria-controls="studio-workspace-navigation"
        aria-expanded={mobileOpen}
        aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
        className="studio-mobile-nav-trigger"
        onClick={toggleMobile}
        ref={mobileTriggerRef}
        type="button"
      >
        <svg aria-hidden="true" height="20" viewBox="0 0 20 20" width="20">
          {mobileOpen ? (
            <path d="M4 4l12 12M16 4L4 16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
          ) : (
            <path d="M3 5h14M3 10h14M3 15h14" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
          )}
        </svg>
      </button>
      {mobileOpen ? (
        <button
          aria-label="Dismiss navigation"
          className="studio-sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          type="button"
        />
      ) : null}
      <aside
        aria-hidden={isMobile && !mobileOpen ? true : undefined}
        className="studio-sidebar"
        data-collapsed={collapsed}
        data-mobile-open={mobileOpen}
        id="studio-workspace-navigation"
        inert={isMobile && !mobileOpen ? true : undefined}
      >
      <div className="studio-sidebar__brand-row">
        <Link className="studio-wordmark" href="/dashboard">
          <span aria-hidden="true" className="studio-wordmark__mark">W</span>
          <span className="studio-wordmark__text">Wavia Studio</span>
        </Link>
        <button
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="studio-sidebar__toggle"
          onClick={toggleCollapsed}
          type="button"
        >
          <span aria-hidden="true">{collapsed ? ">" : "<"}</span>
        </button>
      </div>

      {tenantName ? (
        <div className="studio-workspace" title={tenantName}>
          <span aria-hidden="true" className="studio-workspace__mark">{tenantName.slice(0, 1).toUpperCase()}</span>
          <span className="studio-workspace__copy">
            <span className="studio-workspace__eyebrow">Workspace</span>
            <strong>{tenantName}</strong>
          </span>
        </div>
      ) : null}

      <nav aria-label="Workspace" className="studio-sidebar__navigation">
        {GROUPS.map((group) => {
          const permitted = group.items.filter((item) => hasWorkspaceCapability(capabilities, item.permission));
          if (permitted.length === 0) return null;
          return (
            <div className="studio-nav-group" key={group.label}>
              <p className="studio-nav-group__label">{group.label}</p>
              {permitted.map((item) => {
                const current = item.active(pathname);
                return (
                  <Link aria-current={current ? "page" : undefined} className="studio-nav-link" href={item.href} key={item.label} onClick={() => setMobileOpen(false)} title={collapsed ? item.label : undefined}>
                    <span aria-hidden="true" className="studio-nav-link__glyph">{item.shortLabel}</span>
                    {item.screenReaderPrefix ? <span className="sr-only">{item.screenReaderPrefix} </span> : null}
                    <span className="studio-nav-link__label">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {displayName ? (
        <div className="studio-account">
          <span aria-hidden="true" className="studio-account__avatar">{displayName.slice(0, 1).toUpperCase()}</span>
          <div className="studio-account__identity">
            <strong>{displayName}</strong>
            <span>{role.replaceAll("_", " ")}</span>
          </div>
          {signOutAction ? (
            <form action={signOutAction}>
              <button className="studio-account__signout" type="submit" title="Sign out">
                <span aria-hidden="true">-&gt;</span>
                <span className="studio-account__signout-label">Sign out</span>
              </button>
            </form>
          ) : null}
        </div>
      ) : null}
      </aside>
    </>
  );
}
