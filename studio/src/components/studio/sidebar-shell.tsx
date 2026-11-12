"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import {
  getSidebarPreferenceSnapshot,
  setSidebarPreference,
  subscribeSidebarPreference,
} from "@/features/workspaces/sidebar-preference";

export type SidebarItem = {
  label: string;
  shortLabel: string;
  screenReaderPrefix?: string;
  href: string;
  active(pathname: string): boolean;
};

export type SidebarGroup = { label: string; items: ReadonlyArray<SidebarItem> };

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

export const startsWith = (prefix: string) => (pathname: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);

/**
 * Shared Studio sidebar: collapse preference, mobile drawer, Escape-to-close and focus return.
 * Callers pass groups that are already filtered by server-provided capabilities.
 */
export function SidebarShell({
  account,
  brandHref,
  brandText,
  context,
  groups,
  id,
  navLabel,
}: {
  account?: { displayName: string; roleLabel: string; signOutAction?: () => Promise<void> };
  brandHref: string;
  brandText: string;
  context?: ReactNode;
  groups: ReadonlyArray<SidebarGroup>;
  id: string;
  navLabel: string;
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
        aria-controls={id}
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
        id={id}
        inert={isMobile && !mobileOpen ? true : undefined}
      >
      <div className="studio-sidebar__brand-row">
        <Link className="studio-wordmark" href={brandHref}>
          <span aria-hidden="true" className="studio-wordmark__mark">W</span>
          <span className="studio-wordmark__text">{brandText}</span>
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

      {context}

      <nav aria-label={navLabel} className="studio-sidebar__navigation">
        {groups.map((group) => {
          if (group.items.length === 0) return null;
          return (
            <div className="studio-nav-group" key={group.label}>
              <p className="studio-nav-group__label">{group.label}</p>
              {group.items.map((item) => {
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

      {account ? (
        <div className="studio-account">
          <span aria-hidden="true" className="studio-account__avatar">{account.displayName.slice(0, 1).toUpperCase()}</span>
          <div className="studio-account__identity">
            <strong>{account.displayName}</strong>
            <span>{account.roleLabel}</span>
          </div>
          {account.signOutAction ? (
            <form action={account.signOutAction}>
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
