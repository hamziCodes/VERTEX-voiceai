import type { ReactNode } from "react";

import { requireWorkspace } from "@/auth/workspace";
import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";
import { signOutAction } from "@/features/workspaces/actions";

export default async function StudioLayout({ children }: Readonly<{ children: ReactNode }>) {
  const { membership, session } = await requireWorkspace();
  return (
    <div>
      <header>
        <strong>{membership.tenant_name}</strong>
        <span>{session.displayName}</span>
        <form action={signOutAction}><button type="submit">Sign out</button></form>
      </header>
      <WorkspaceNavigation role={membership.role} />
      <main>{children}</main>
    </div>
  );
}
