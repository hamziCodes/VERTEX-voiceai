"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { FormDialog } from "@/components/studio/form-dialog";
import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";
import type { APIKeyDto, CreateApiKeyResponseDto } from "@/data/schema";
import { formatDate } from "@/lib/format";

import type { CreateAPIKeyInput } from "./types";

export interface APIKeyManagerProps {
  keys: APIKeyDto[];
  canManage: boolean;
  onCreate: (input: CreateAPIKeyInput) => Promise<CreateApiKeyResponseDto>;
  onRevoke: (keyId: string) => Promise<{ success: boolean; error?: string }>;
}

const KEY_ROLES: ReadonlyArray<{ value: CreateAPIKeyInput["role"]; label: string; description: string }> = [
  { value: "tenant_viewer", label: "Read and mint sessions", description: "Machine role tenant_viewer. Recommended for a server that only starts voice sessions." },
  { value: "tenant_editor", label: "Edit and mint sessions", description: "Machine role tenant_editor. Also allows editor-level API access." },
];

function keyStatus(key: APIKeyDto): { label: string; tone: "success" | "danger" | "neutral" } {
  if (key.revoked_at) return { label: "Revoked", tone: "danger" };
  if (key.expires_at && new Date(key.expires_at) < new Date()) return { label: "Expired", tone: "neutral" };
  return { label: "Active", tone: "success" };
}

export function APIKeyManager({ keys, canManage, onCreate, onRevoke }: APIKeyManagerProps) {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createdResult, setCreatedResult] = useState<CreateApiKeyResponseDto | null>(null);

  const [name, setName] = useState("");
  const [role, setRole] = useState<CreateAPIKeyInput["role"]>("tenant_viewer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [revokingKey, setRevokingKey] = useState<APIKeyDto | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  async function handleCreateSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setFormError(null);
    try {
      const res = await onCreate({
        name: name.trim(),
        role,
        scopes: ["session:mint"],
      });
      setIsCreateOpen(false);
      setName("");
      setCreatedResult(res);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create key.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmRevoke() {
    if (!revokingKey) return;
    setIsRevoking(true);
    setRevokeError(null);
    try {
      const result = await onRevoke(revokingKey.key_id);
      if (result.success) {
        setRevokingKey(null);
      } else {
        setRevokeError(result.error ?? "Failed to revoke API key.");
      }
    } catch (error) {
      setRevokeError(error instanceof Error ? error.message : "Failed to revoke API key.");
    } finally {
      setIsRevoking(false);
    }
  }

  return (
    <div className="developer-view">
      <section aria-labelledby="api-keys-list-heading" className="form-panel">
        <div className="developer-toolbar">
          <div>
            <h2 id="api-keys-list-heading">Workspace keys</h2>
            <p className="muted-copy">Keys mint short-lived voice sessions from your server. Only the prefix is ever shown after creation.</p>
          </div>
          {canManage ? (
            <button className="button button--primary" onClick={() => { setFormError(null); setIsCreateOpen(true); }} type="button">
              Create API key
            </button>
          ) : null}
        </div>
        {!canManage ? <p className="inline-notice inline-notice--info">Your role can view API keys but cannot create or revoke them.</p> : null}

        {keys.length === 0 ? (
          <p className="muted-copy developer-empty">No API keys created yet.</p>
        ) : (
          <table aria-label="API keys" className="data-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Key prefix</th>
                <th scope="col">Role</th>
                <th scope="col">Scopes</th>
                <th scope="col">Created</th>
                <th scope="col">Status</th>
                {canManage ? <th scope="col"><span className="sr-only">Actions</span></th> : null}
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => {
                const status = keyStatus(k);
                return (
                  <tr key={k.key_id}>
                    <td data-label="Name"><strong>{k.name}</strong></td>
                    <td data-label="Key prefix"><span className="technical-value">{k.key_prefix}...</span></td>
                    <td data-label="Role"><span className="technical-value">{k.role}</span></td>
                    <td data-label="Scopes">
                      <span className="token-list">{k.scopes.map((s) => <code className="technical-value" key={s}>{s}</code>)}</span>
                    </td>
                    <td data-label="Created">{formatDate(k.created_at)}</td>
                    <td data-label="Status"><StatusBadge tone={status.tone}>{status.label}</StatusBadge></td>
                    {canManage ? (
                      <td className="data-table__actions" data-label="Actions">
                        {status.label === "Active" ? (
                          <button
                            aria-label={`Revoke ${k.name}`}
                            className="button button--quiet-danger"
                            onClick={() => { setRevokingKey(k); setRevokeError(null); }}
                            type="button"
                          >
                            Revoke
                          </button>
                        ) : null}
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {isCreateOpen ? (
        <FormDialog
          busy={isSubmitting}
          description="The key is shown once after creation. Store it in your server's secret manager or environment, never in browser code."
          error={formError}
          onCancel={() => setIsCreateOpen(false)}
          onSubmit={(event) => void handleCreateSubmit(event)}
          submitDisabled={!name.trim()}
          submitLabel="Generate key"
          title="Create API key"
        >
          <FormField hint="For example Production web client." label="Key name" name="key-name">
            <input maxLength={128} onChange={(e) => setName(e.target.value)} required type="text" value={name} />
          </FormField>
          <fieldset className="choice-grid">
            <legend className="choice-grid__legend">Role</legend>
            {KEY_ROLES.map((option) => (
              <label className="choice-card" key={option.value}>
                <input checked={role === option.value} name="key-role" onChange={() => setRole(option.value)} type="radio" value={option.value} />
                <span className="choice-card__copy">
                  <strong>{option.label}</strong>
                  <span>{option.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </FormDialog>
      ) : null}

      {createdResult ? <SecretReveal onDone={() => setCreatedResult(null)} secret={createdResult.api_key} /> : null}

      {revokingKey ? (
        <ConfirmDialog
          busy={isRevoking}
          confirmLabel="Confirm revoke"
          error={revokeError}
          onCancel={() => { setRevokingKey(null); setRevokeError(null); }}
          onConfirm={() => void handleConfirmRevoke()}
          title="Revoke API key"
        >
          <p>Are you sure you want to revoke “{revokingKey.name}”? Any services using this key will immediately lose access.</p>
        </ConfirmDialog>
      ) : null}
    </div>
  );
}

/** One-time secret reveal: cannot be dismissed (Escape or Done) until the person confirms they copied it. */
function SecretReveal({ onDone, secret }: { onDone(): void; secret: string }) {
  const titleId = useId();
  const [acknowledged, setAcknowledged] = useState(false);
  const [hasCopied, setHasCopied] = useState(false);
  const copyRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    copyRef.current?.focus();
  }, []);

  async function copy() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(secret);
      setHasCopied(true);
    }
  }

  return (
    <div className="studio-dialog-backdrop">
      <div aria-labelledby={titleId} aria-modal="true" className="studio-dialog studio-dialog--secret" role="dialog">
        <h2 id={titleId}>Save this secret key now</h2>
        <p className="studio-dialog__body">You will not be able to see it again. Copy it into your server&apos;s secret manager or environment variables.</p>
        <pre className="secret-value">{secret}</pre>
        <div className="studio-dialog__actions studio-dialog__actions--start">
          <button className="button button--secondary" onClick={() => void copy()} ref={copyRef} type="button">
            {hasCopied ? "Copied" : "Copy to clipboard"}
          </button>
        </div>
        <label className="checkbox-row">
          <input aria-label="I have copied this secret key" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} type="checkbox" />
          <span>I have copied this secret key</span>
        </label>
        <div className="studio-dialog__actions">
          <button className="button button--primary" disabled={!acknowledged} onClick={onDone} type="button">Done</button>
        </div>
      </div>
    </div>
  );
}
