'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useOrganizationList, useClerk } from '@clerk/nextjs';
import { Building2, Lock } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ORG_ACCESS_CONFIGURED, isAllowedOrgRecord, safeRedirectPath } from '@/shared/org-access';

type Phase = 'checking' | 'activating' | 'denied' | 'unconfigured' | 'error';

/**
 * Resolves the three states a signed-in user can be in when the middleware bounces them here.
 *
 *   1. They ARE a member of the allowed organization, but it is not the active one — usually
 *      because they have simply never selected it. We activate it and send them on. This is
 *      not a decision the user should have to make: there is exactly one organization they
 *      could pick.
 *
 *   2. They are NOT a member. They are told so, plainly, and offered a way out.
 *
 *   3. The deployment has no organization configured at all. That is an operator error, and
 *      saying "you need an invitation" to someone who already holds one would be a lie.
 *
 * The denial message names no organization, no member count, and no reason beyond
 * "you are not a member". A denial screen that says *which* organization exists, or how many
 * people are in it, hands an attacker the map.
 */
export function SelectOrganizationClient(): React.JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signOut } = useClerk();
  const { isLoaded, setActive, userMemberships } = useOrganizationList({
    userMemberships: { infinite: true },
  });

  const [phase, setPhase] = useState<Phase>('checking');

  useEffect(() => {
    if (!isLoaded || !setActive) return;
    if (userMemberships.isLoading) return;

    /**
     * No organization configured at all means every request is denied. That is deliberate
     * (see `org-access.ts`), but it is an operator error, not a user error — say so, rather
     * than telling a legitimate user they lack an invitation they in fact hold.
     */
    if (!ORG_ACCESS_CONFIGURED) {
      setPhase('unconfigured');
      return;
    }

    // Slug first (stable across instances), org id as the fallback that survives slugs
    // being disabled. `isAllowedOrgRecord` applies exactly the rule the middleware applies.
    const membership = userMemberships.data?.find((m) => isAllowedOrgRecord(m.organization));

    if (!membership) {
      setPhase('denied');
      return;
    }

    setPhase('activating');

    void (async () => {
      try {
        await setActive({ organization: membership.organization.id });

        /**
         * `redirect_url` arrives from the middleware and is therefore attacker-influencable:
         * a link to `/select-organization?redirect_url=https://evil.example` would otherwise
         * bounce a freshly authenticated user onto someone else's page from our domain.
         * `safeRedirectPath` permits only same-origin paths.
         */
        const target = safeRedirectPath(searchParams.get('redirect_url'), window.location.origin);
        router.replace(target);
      } catch {
        setPhase('error');
      }
    })();
  }, [isLoaded, setActive, userMemberships.isLoading, userMemberships.data, router, searchParams]);

  if (phase === 'checking' || phase === 'activating') {
    return (
      <Panel icon={<Building2 className="h-6 w-6" aria-hidden="true" />} title="Opening your workspace">
        <p className="text-sm text-muted-foreground" role="status">
          {phase === 'activating' ? 'Signing you in to your organization…' : 'Checking your access…'}
        </p>
      </Panel>
    );
  }

  if (phase === 'unconfigured') {
    return (
      <Panel icon={<Building2 className="h-6 w-6" aria-hidden="true" />} title="This workspace is not configured">
        {/*
          An operator error, stated as one. Naming the missing variable is safe — it is a
          deployment-configuration name, not a secret, and the person seeing this screen
          cannot fix it without knowing.
        */}
        <p className="max-w-md text-sm text-muted-foreground">
          No organization has been authorised for this deployment. An administrator must set{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">NEXT_PUBLIC_CLERK_ALLOWED_ORG_SLUG</code>. Until then,
          access is denied to everyone — including you.
        </p>
        <Button variant="outline" onClick={() => void signOut({ redirectUrl: '/sign-in' })}>
          Sign out
        </Button>
      </Panel>
    );
  }

  if (phase === 'error') {
    return (
      <Panel icon={<Building2 className="h-6 w-6" aria-hidden="true" />} title="Could not open your workspace">
        <p className="max-w-md text-sm text-muted-foreground">
          Something went wrong while opening your organization. Try again, and contact your administrator if it
          persists.
        </p>
        <Button variant="outline" onClick={() => router.refresh()}>
          Try again
        </Button>
      </Panel>
    );
  }

  return (
    <Panel icon={<Lock className="h-6 w-6" aria-hidden="true" />} title="You do not have access">
      {/*
        State the rule, never the data. Naming the organization, or hinting that it exists,
        would tell an attacker exactly what to target.
      */}
      <p className="max-w-md text-sm text-muted-foreground">
        Your account is not a member of an organization with access to this dashboard. Access is granted by
        invitation. Ask your organization owner to invite you, then sign in again.
      </p>
      <Button variant="outline" onClick={() => void signOut({ redirectUrl: '/sign-in' })}>
        Sign out
      </Button>
    </Panel>
  );
}

function Panel({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <Card className="w-full max-w-xl">
        <div className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            {icon}
          </div>
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          {children}
        </div>
      </Card>
    </main>
  );
}
