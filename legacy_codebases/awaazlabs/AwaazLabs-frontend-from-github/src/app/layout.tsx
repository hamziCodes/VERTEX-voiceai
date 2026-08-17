import type { Metadata, Viewport } from 'next';
import React from 'react';
import { ClerkProvider } from '@clerk/nextjs';

import './globals.css';
import { LocaleProvider } from '@/i18n/locale-context';
import { LOCALE_BCP47, DEFAULT_LOCALE } from '@/i18n/config';

export const metadata: Metadata = {
  title: {
    default: 'AwaazLabs Client Dashboard',
    template: '%s · AwaazLabs',
  },
  description:
    'Voice AI operations for multi-location clinics: appointments, insurance verification, conversations, and the Qualicall quality loop.',
  // This dashboard renders patient-level data in PHI mode. It must never be indexed, and
  // no referrer may leak a patient-scoped URL to a third party.
  robots: { index: false, follow: false, nocache: true },
  referrer: 'strict-origin-when-cross-origin',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

/**
 * Root layout.
 *
 * Holds only what *every* page needs — including `/sign-in`, which must not render inside
 * the dashboard chrome. `SessionProvider` and `DashboardShell` therefore live in
 * `(dashboard)/layout.tsx`; a route group adds no URL segment, so every route keeps its
 * path.
 *
 * `ClerkProvider` wraps both: the sign-in page needs it to render `<SignIn />`, and the
 * dashboard needs it to read the signed-in user's role.
 */
export default function RootLayout({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    // §2.7: rendered with the shipped default locale; `LocaleProvider` keeps this attribute
    // truthful when the locale changes, so assistive technology never announces Spanish
    // content as English.
    <html lang={LOCALE_BCP47[DEFAULT_LOCALE]}>
      <body>
        <ClerkProvider>
          <LocaleProvider>{children}</LocaleProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}
