import "server-only";

import { withAuth } from "@workos-inc/authkit-nextjs";

export interface StudioSession {
  userId: string;
  email: string | null;
  displayName: string;
  accessToken: string;
}

export async function requireSession(): Promise<StudioSession> {
  const session = await withAuth({ ensureSignedIn: true });
  if (!session.user?.id || !session.accessToken) {
    throw new Error("WorkOS returned an incomplete session.");
  }
  const displayName = [session.user.firstName, session.user.lastName].filter(Boolean).join(" ");
  return {
    userId: session.user.id,
    email: session.user.email ?? null,
    displayName: displayName || session.user.email || "Wavia user",
    accessToken: session.accessToken,
  };
}
