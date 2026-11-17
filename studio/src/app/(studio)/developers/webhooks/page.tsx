import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { controlPlaneRequest } from "@/data/control-plane";
import { webhookTargetListSchema } from "@/data/schema";
import { createWebhookTargetAction, disableWebhookTargetAction } from "@/features/webhooks/actions";
import { WebhookManager } from "@/features/webhooks/webhook-manager";

export default async function WebhooksPage() {
  const { membership, session } = await requireWorkspace("webhook:read");
  const targets = await controlPlaneRequest("/v1/webhook-targets", {
    schema: webhookTargetListSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
  const canManage = hasWorkspaceCapability(membership.capabilities, "webhook:write");

  return (
    <section className="developer-page">
      <PageHeader
        eyebrow="Developer"
        summary="Receive each call's summary and extracted fields when post-call processing finishes. Calls the review policy flags are held until someone approves them."
        title="Webhooks"
      />
      <WebhookManager canManage={canManage} onCreate={createWebhookTargetAction} onDisable={disableWebhookTargetAction} targets={targets} />
      <section aria-labelledby="webhook-verify-title" className="form-panel integration-details">
        <h2 id="webhook-verify-title">Verifying deliveries</h2>
        <p className="muted-copy">
          Each delivery is a JSON <code>POST</code> with event <code>post_call.intelligence.completed</code>. <code>X-Wavia-Signature</code> is the hex HMAC-SHA256 of the raw body using your signing secret; <code>X-Idempotency-Key</code> is stable across retries.
        </p>
        <pre className="integration-details__snippet"><code>{`import hmac, hashlib

def is_from_wavia(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)`}</code></pre>
      </section>
    </section>
  );
}
