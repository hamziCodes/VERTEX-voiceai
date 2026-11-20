import { requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { loadOperationsSnapshot } from "@/features/admin/data";
import { OperationsView } from "@/features/admin/operations-view";

export default async function OperationsPage() {
  const { session } = await requirePlatform("platform_operations:read");
  const snapshot = await loadOperationsSnapshot(session);

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="A point-in-time snapshot of the signals the control plane can observe. Values and secrets are never shown, only whether something is configured."
        title="Operations"
      />
      <OperationsView snapshot={snapshot} />
    </section>
  );
}
