"use client";

import { useState, useTransition } from "react";

import { FormField } from "@/components/studio/form-field";
import { StatePanel } from "@/components/studio/state-panel";
import { StatusBadge } from "@/components/studio/status-badge";
import type { CreatedWebhookTargetDto, WebhookTargetDto } from "@/data/schema";

import type { CreateWebhookResult } from "./actions";

const STATE_TONES = { active: "success", pending: "warning", disabled: "neutral" } as const;

export function WebhookManager({
  targets,
  canManage,
  onCreate,
  onDisable,
}: {
  targets: WebhookTargetDto[];
  canManage: boolean;
  onCreate: (input: { name: string; url: string }) => Promise<CreateWebhookResult>;
  onDisable: (targetId: string) => Promise<{ ok: boolean }>;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedWebhookTargetDto | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [pending, startTransition] = useTransition();

  function create(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      const result = await onCreate({ name, url });
      if (result.state === "error") {
        setError(result.message);
        return;
      }
      setCreated(result.target);
      setAcknowledged(false);
      setName("");
      setUrl("");
    });
  }

  return (
    <div className="webhook-manager">
      {created ? (
        <div className="studio-dialog-backdrop">
          <div aria-labelledby="webhook-secret-title" aria-modal="true" className="studio-dialog studio-dialog--secret" role="dialog">
            <h2 id="webhook-secret-title">Save this signing secret now</h2>
            <p className="studio-dialog__body">
              Use it to verify <code>{created.signature_header}</code> on every delivery to <strong>{created.name}</strong>. You will not see it again.
            </p>
            <pre className="secret-value">{created.signing_secret}</pre>
            <label className="studio-dialog__confirm">
              <input aria-label="I have saved this signing secret" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} type="checkbox" />
              <span>I have saved this signing secret</span>
            </label>
            <div className="studio-dialog__actions">
              <button className="button button--primary" disabled={!acknowledged} onClick={() => setCreated(null)} type="button">Done</button>
            </div>
          </div>
        </div>
      ) : null}

      {canManage ? (
        <form className="form-panel webhook-manager__create" onSubmit={create}>
          <h2>Add an endpoint</h2>
          <FormField hint="Shown in delivery history." label="Endpoint name" name="webhook-name">
            <input maxLength={128} onChange={(event) => setName(event.target.value)} required value={name} />
          </FormField>
          <FormField hint="HTTPS on port 443, reachable from the internet." label="Endpoint URL" name="webhook-url">
            <input inputMode="url" onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/wavia/events" required type="url" value={url} />
          </FormField>
          {error ? <p className="inline-notice inline-notice--danger" role="alert">{error}</p> : null}
          <button className="button button--primary" disabled={pending} type="submit">{pending ? "Adding…" : "Add endpoint"}</button>
        </form>
      ) : null}

      {targets.length === 0 ? (
        <StatePanel description="Add an endpoint to receive each call's summary and extracted fields when post-call processing finishes." title="No webhook endpoints yet" />
      ) : (
        <ul aria-label="Webhook endpoints" className="webhook-manager__list">
          {targets.map((target) => (
            <li aria-label={target.name} className="form-panel webhook-manager__item" key={target.target_id}>
              <div>
                <strong>{target.name}</strong>
                <p className="technical-value">{target.url}</p>
              </div>
              <StatusBadge tone={STATE_TONES[target.state]}>{target.state === "active" ? "Active" : target.state === "disabled" ? "Disabled" : "Pending"}</StatusBadge>
              {canManage && target.state === "active" ? (
                <button
                  className="button button--secondary"
                  disabled={pending}
                  onClick={() => startTransition(async () => { await onDisable(target.target_id); })}
                  type="button"
                >
                  Disable
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
