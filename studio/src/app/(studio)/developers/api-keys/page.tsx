import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { listAPIKeys } from "@/features/api-keys/data";
import { createAPIKeyAction, revokeAPIKeyAction } from "@/features/api-keys/actions";
import { APIKeyManager } from "@/features/api-keys/api-key-manager";

export default async function APIKeysPage() {
  const { membership } = await requireWorkspace("api_key:read");
  const keys = await listAPIKeys();
  const canManage = hasWorkspaceCapability(membership.capabilities, "api_key:write");

  async function handleCreate(input: Parameters<typeof createAPIKeyAction>[0]) {
    "use server";
    const res = await createAPIKeyAction(input);
    if (!res.success || !res.data) {
      throw new Error(res.error ?? "Failed to create API key.");
    }
    return res.data;
  }

  return (
    <APIKeyManager
      keys={keys}
      canManage={canManage}
      onCreate={handleCreate}
      onRevoke={revokeAPIKeyAction}
    />
  );
}
