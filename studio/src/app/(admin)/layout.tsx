import type { ReactNode } from "react";

import { requirePlatform } from "@/auth/platform";
import { AdminNavigation } from "@/features/admin/admin-navigation";
import { signOutAction } from "@/features/workspaces/actions";

/** Internal Wavia area. Customers receive not-found from `requirePlatform`; FastAPI re-checks every request. */
export default async function AdminLayout({ children }: Readonly<{ children: ReactNode }>) {
  const { identity, session } = await requirePlatform();
  return (
    <div className="studio-shell" data-density="compact" data-studio-area="internal" data-vertex-surface="dashboard">
      <AdminNavigation capabilities={identity.capabilities} displayName={session.displayName} role={identity.role} signOutAction={signOutAction} />
      <div className="studio-frame">
        <main className="studio-main">{children}</main>
      </div>
    </div>
  );
}
