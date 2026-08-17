import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import React from 'react';
import { SignIn } from '@clerk/nextjs';

import { DEBUG_BYPASS_AUTH } from '@/shared/debug-auth';

export const metadata: Metadata = {
  title: 'Sign in',
  robots: { index: false, follow: false },
};

/**
 * Sign-in. Spec §2.3 lists `login` as an audited event; the audit row is written once the
 * session is established (see `SessionProvider`).
 *
 * Catch-all `[[...sign-in]]` is required, not decorative: Clerk routes its own sub-steps
 * (second factor, SSO callback, password reset) beneath this path. A plain `/sign-in`
 * would 404 the moment MFA is enabled — which §16.3 requires for Owner and Manager in PHI
 * mode.
 *
 * There is no `/sign-up` route, by design. §16.3: members are added by "invite by email
 * with role assignment (Owner only)". A public registration form on a dashboard that
 * renders patient data is a liability, not a feature. Sign-up is also disabled in the Clerk
 * dashboard, because omitting the route here would not stop someone reaching Clerk's hosted
 * sign-up page directly.
 *
 * Styling: Clerk's `appearance.variables` runs colour math (it derives hover and focus
 * shades from each value), which cannot resolve a CSS custom property like
 * `hsl(var(--primary))`. So the theme is applied through `appearance.elements` as Tailwind
 * classes, every one of which is bound to a token in THEME_NOTES.md. No literal colour is
 * introduced.
 */
export default function SignInPage(): React.JSX.Element {
  // DEBUG: skip email / MFA sign-in — middleware also redirects here to `/`.
  if (DEBUG_BYPASS_AUTH) redirect('/');

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4 py-12">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Awaaz</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Client dashboard for voice AI operations. Access is granted by invitation.
        </p>
      </div>

      <SignIn
        // Where to land when Clerk has no stored return-to URL.
        fallbackRedirectUrl="/"
        appearance={{
          elements: {
            rootBox: 'w-full max-w-md',
            cardBox: 'w-full shadow-sm',
            card: 'bg-card border border-border rounded-lg shadow-sm',
            headerTitle: 'text-foreground text-lg font-semibold tracking-tight',
            headerSubtitle: 'text-muted-foreground text-sm',
            socialButtonsBlockButton: 'border border-border bg-card text-foreground hover:bg-accent',
            dividerLine: 'bg-border',
            dividerText: 'text-muted-foreground',
            formFieldLabel: 'text-foreground text-sm font-medium',
            formFieldInput:
              'border border-input bg-background text-foreground rounded-md focus-visible:ring-2 focus-visible:ring-ring',
            formButtonPrimary:
              'bg-primary text-primary-foreground hover:bg-primary/90 rounded-md text-sm font-medium normal-case',
            footerActionText: 'text-muted-foreground',
            footerActionLink: 'text-foreground hover:underline',
            identityPreviewEditButton: 'text-foreground',
            formFieldAction: 'text-foreground hover:underline',
            // §16.3 will require MFA for Owner and Manager. Style the factor steps now so
            // enabling it later does not ship an unstyled screen.
            formResendCodeLink: 'text-foreground hover:underline',
            otpCodeFieldInput: 'border border-input bg-background text-foreground',
            // No sign-up exists; hide the affordance rather than rely on Clerk's default.
            footer: 'hidden',
          },
        }}
      />

      <p className="max-w-sm text-center text-xs text-muted-foreground">
        This workspace may render protected health information. Sessions are audited.
      </p>
    </main>
  );
}
