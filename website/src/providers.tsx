import type { ReactNode } from 'react';

/**
 * ⚠️ App-wide providers. Add new providers here — they'll be available in all routes.
 * Do NOT add another router anywhere. The single BrowserRouter lives in main.tsx.
 *
 * There is no ThemeProvider by design: Theme B is the only polarity. If you are
 * about to add a theme switch, read docs/design/scroll-story.md §0 first.
 */
export function AppProviders({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
