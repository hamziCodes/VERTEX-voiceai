import type { ReactNode } from "react";

import { requireWorkspace } from "@/auth/workspace";
import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";
import { signOutAction } from "@/features/workspaces/actions";

export default async function StudioLayout({ children }: Readonly<{ children: ReactNode }>) {
  const { membership, session } = await requireWorkspace();
  return (
    <div className="studio-shell" data-vertex-surface="dashboard" data-density="compact">
      <WorkspaceNavigation capabilities={membership.capabilities} displayName={session.displayName} role={membership.role} signOutAction={signOutAction} tenantName={membership.tenant_name} />
      <div className="studio-frame">
        <main className="studio-main">{children}</main>
      </div>
    </div>
  );
}
