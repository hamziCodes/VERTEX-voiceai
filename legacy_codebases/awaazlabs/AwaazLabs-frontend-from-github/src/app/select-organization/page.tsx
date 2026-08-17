import type { Metadata } from 'next';
import React, { Suspense } from 'react';

import { SelectOrganizationClient } from './select-organization-client';

export const metadata: Metadata = {
  title: 'Opening your workspace',
  robots: { index: false, follow: false },
};

/**
 * Reached only when a signed-in user's active organization is not the one this dashboard
 * belongs to — including the common case of a member who has never selected an organization.
 *
 * Lives outside the `(dashboard)` route group: it must render without the dashboard shell,
 * because the user may have no right to see the shell at all.
 *
 * `Suspense` is required because the client reads `useSearchParams()`. The fallback says
 * something rather than nothing: a blank screen during an auth redirect reads as a broken
 * app, and this page is only ever seen mid-redirect.
 */
export default function SelectOrganizationPage(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-background">
          <span role="status" className="text-sm text-muted-foreground">
            Checking your access…
          </span>
        </main>
      }
    >
      <SelectOrganizationClient />
    </Suspense>
  );
}
