'use client';

/**
 * SESSION CONTEXT — spec §2.1 (mode), §2.2 (role), §2.4 (location filter).
 *
 * FROZEN FILE (Foundation).
 *
 * `'use client'` is required and not incidental: mode, the location filter, and the audit
 * writer (§2.3) are all client state. Route `page.tsx` files stay server components and
 * delegate to a `*-client.tsx` child, preserving the pattern already used in this repo.
 *
 * ## Where `role` comes from
 *
 * The signed-in Clerk user's `publicMetadata.role`, validated against the canonical `ROLES`
 * union. An unknown value, a missing value, or a malformed one **fails closed to
 * `VIEWER`** — never open. Setting a user's role is done in the Clerk dashboard until
 * §16.3's Members page exists.
 *
 * The demo role/mode switchers still exist, because the guide (Part F.3) requires every
 * gated surface to be exercisable. But they are compiled out of production builds
 * (`DEMO_CONTROLS_ENABLED`). In a deployed build there is no way to self-promote: the role
 * is whatever Clerk says it is.
 *
 * **None of this is the security boundary.** §2.2: "Permission checks are server-side. The
 * UI hides what the role cannot access; the API independently rejects it." Client-side role
 * gating decides what renders. Authentication is enforced in `src/middleware.ts`, and a real
 * backend must re-check authorization on every request regardless of what this file says.
 */

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useUser } from '@clerk/nextjs';

import type { Session } from '@/mock/data-access';
import { seedLoginEvent } from '@/shared/audit';
import { DATA_MODES, ROLES } from '@/shared/status-models';
import type { DataMode, Role } from '@/shared/status-models';
import { DEBUG_ACTOR, DEBUG_BYPASS_AUTH, DEBUG_ROLE } from '@/shared/debug-auth';
import { DEFAULT_ORG_ID, getOrgById } from '@/mock/orgs';
import { isMultiLocation } from '@/mock/schema';
import type { MockOrganization } from '@/mock/schema';

/**
 * Demo role/mode switchers are development-only. `process.env.NODE_ENV` is statically
 * replaced at build time, so in production this is `false` and the switcher markup is
 * removed by dead-code elimination — it is not merely hidden with CSS.
 */
export const DEMO_CONTROLS_ENABLED = process.env.NODE_ENV !== 'production';

interface SessionContextValue {
  readonly session: Session;
  readonly org: MockOrganization;
  /** §2.4: "Single-location clinics see no filter." */
  readonly showLocationFilter: boolean;
  /** The role Clerk actually granted, before any development-only override. */
  readonly authenticatedRole: Role;
  /** No-op in production builds. */
  readonly setRole: (role: Role) => void;
  readonly setMode: (mode: DataMode) => void;
  readonly setOrgId: (orgId: string) => void;
  readonly setLocationId: (locationId: string | null) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within <SessionProvider>');
  return ctx;
}

const STORAGE_KEY = 'awaazlabs.session';

/**
 * §2.2's least-privileged role. Anything unrecognised lands here.
 *
 * Choosing `VIEWER` rather than throwing is deliberate: a user whose metadata an admin has
 * not set yet should see the aggregate dashboard, not an error page. What they must never
 * do is silently receive Owner privileges.
 */
const FAIL_CLOSED_ROLE: Role = 'VIEWER';

/** Read `publicMetadata.role` and validate it. Never trusts the shape. */
function roleFromClerkMetadata(metadata: unknown): Role {
  if (typeof metadata !== 'object' || metadata === null) return FAIL_CLOSED_ROLE;
  const candidate = (metadata as Record<string, unknown>).role;
  if (typeof candidate !== 'string') return FAIL_CLOSED_ROLE;
  return (ROLES as readonly string[]).includes(candidate) ? (candidate as Role) : FAIL_CLOSED_ROLE;
}

/** Only workspace preferences persist. `role` never does — it comes from Clerk every load. */
interface PersistedSession {
  mode: DataMode;
  orgId: string;
  locationId: string | null;
}

/**
 * §2.4: "A global location filter sits in the top bar and **persists across tabs**."
 *
 * Client-side navigation preserves React state, but a hard reload does not — and a filter
 * that silently resets to "all locations" on refresh will quietly mislead someone reading
 * numbers for one clinic.
 *
 * `role` is deliberately absent from this payload. Persisting it would let a user edit
 * `localStorage` and change what the dashboard renders for them. The role is re-derived from
 * the Clerk session on every load.
 */
function readPersisted(): Partial<PersistedSession> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return {};
    const p = parsed as Partial<PersistedSession>;

    const out: Partial<PersistedSession> = {};
    if (p.mode && (DATA_MODES as readonly string[]).includes(p.mode)) out.mode = p.mode;
    if (typeof p.orgId === 'string' && getOrgById(p.orgId)) out.orgId = p.orgId;
    if (p.locationId === null || typeof p.locationId === 'string') out.locationId = p.locationId;
    return out;
  } catch {
    // Malformed JSON, or localStorage unavailable in private browsing. Defaults are correct.
    return {};
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const { isLoaded, user } = useUser();

  // Always render the defaults first: reading localStorage during the initial render would
  // produce markup that differs from the server's, and React would throw a hydration
  // mismatch. The stored preferences are applied in an effect immediately after mount.
  const [mode, setModeState] = useState<DataMode>('PHI_BAA');
  const [orgId, setOrgIdState] = useState<string>(DEFAULT_ORG_ID);
  const [locationId, setLocationIdState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  /** Development-only override. `null` means "use whatever Clerk granted". */
  const [devRoleOverride, setDevRoleOverride] = useState<Role | null>(null);

  React.useEffect(() => {
    const p = readPersisted();
    if (p.mode) setModeState(p.mode);
    if (p.orgId) setOrgIdState(p.orgId);
    setHydrated(true);
  }, []);

  const authenticatedRole = user
    ? roleFromClerkMetadata(user.publicMetadata)
    : DEBUG_BYPASS_AUTH
      ? DEBUG_ROLE
      : FAIL_CLOSED_ROLE;
  const role = DEMO_CONTROLS_ENABLED && devRoleOverride !== null ? devRoleOverride : authenticatedRole;

  /**
   * §2.3 audit rows name an actor. Before Clerk this was a hardcoded placeholder; now it is
   * the real signed-in identity, so the Audit Log (§16.2) is truthful about who did what.
   */
  const actor = user?.primaryEmailAddress?.emailAddress ?? user?.id ?? (DEBUG_BYPASS_AUTH ? DEBUG_ACTOR : 'unknown');

  const org = getOrgById(orgId);
  if (!org) throw new Error(`Unknown organization: ${orgId}`);

  // A persisted location id from another org must not survive an org switch.
  const scopedLocationId = org.locations.some((l) => l.id === locationId) ? locationId : null;

  const session = useMemo<Session>(
    () => ({ actor, role, mode, orgId, locationId: scopedLocationId }),
    [actor, role, mode, orgId, scopedLocationId],
  );

  // Persist only after hydration, so the first effect pass does not immediately overwrite
  // the stored value with the defaults it was about to replace.
  React.useEffect(() => {
    if (!hydrated) return;
    try {
      const payload: PersistedSession = { mode, orgId, locationId: null };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // Preference simply does not persist. Never break the app over storage.
    }
  }, [hydrated, mode, orgId]);

  /**
   * §2.3 lists `login` as an audited event. It fires once the Clerk user resolves, so the
   * row names the real account — not a placeholder, and not before we know who signed in.
   * `seedLoginEvent` is idempotent, which matters because React double-invokes effects in
   * development strict mode.
   */
  React.useEffect(() => {
    if (!isLoaded && !DEBUG_BYPASS_AUTH) return;
    if (!user && !DEBUG_BYPASS_AUTH) return;
    seedLoginEvent(actor, authenticatedRole, null);
  }, [isLoaded, user, actor, authenticatedRole]);

  // Switching org must clear the location filter: a location id from the previous org is
  // meaningless in the new one, and silently keeping it would scope every query to nothing.
  const setOrgId = useCallback((next: string) => {
    setOrgIdState(next);
    setLocationIdState(null);
  }, []);

  const setLocationId = useCallback((next: string | null) => setLocationIdState(next), []);
  const setMode = useCallback((next: DataMode) => setModeState(next), []);

  /** No-op unless this is a development build. Production has no role switcher at all. */
  const setRole = useCallback((next: Role) => {
    if (!DEMO_CONTROLS_ENABLED) return;
    setDevRoleOverride(next);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      org,
      showLocationFilter: isMultiLocation(org),
      authenticatedRole,
      setRole,
      setMode,
      setOrgId,
      setLocationId,
    }),
    [session, org, authenticatedRole, setRole, setMode, setOrgId, setLocationId],
  );

  /**
   * Middleware guarantees a session exists before this renders, so this branch is a
   * momentary loading state, not an auth check. Rendering the shell against `role = VIEWER`
   * while Clerk resolves would flash a downgraded UI.
   */
  if (!DEBUG_BYPASS_AUTH && !isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <span role="status" className="text-sm text-muted-foreground">
          Loading your workspace…
        </span>
      </div>
    );
  }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
