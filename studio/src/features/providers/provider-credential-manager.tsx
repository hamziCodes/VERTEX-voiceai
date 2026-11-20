"use client";

import { useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { FormDialog } from "@/components/studio/form-dialog";
import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";

import type { CatalogProviderDto, ProviderCredentialDto, StoreCredentialInput } from "./types";

export interface ProviderCredentialManagerProps {
  catalog: CatalogProviderDto[];
  credentials: ProviderCredentialDto[];
  advancedEnabled: boolean;
  canManage: boolean;
  onSave: (input: StoreCredentialInput) => Promise<{ success: boolean; error?: string }>;
  onRevoke: (credentialId: string) => Promise<{ success: boolean; error?: string }>;
}

const CATEGORIES = [
  { key: "stt", label: "Speech-to-text (STT)" },
  { key: "llm", label: "Language models (LLM)" },
  { key: "tts", label: "Text-to-speech (TTS)" },
] as const;

const PROVIDER_NAMES: Readonly<Record<string, string>> = {
  elevenlabs: "ElevenLabs",
  fish_audio: "Fish Audio",
  openai: "OpenAI",
};

function providerName(providerId: string): string {
  return PROVIDER_NAMES[providerId] ?? providerId.charAt(0).toUpperCase() + providerId.slice(1);
}

export function ProviderCredentialManager({
  catalog,
  credentials,
  advancedEnabled,
  canManage,
  onSave,
  onRevoke,
}: ProviderCredentialManagerProps) {
  const [configuringProvider, setConfiguringProvider] = useState<CatalogProviderDto | null>(null);
  const [secret, setSecret] = useState("");
  const [reference, setReference] = useState("default");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [revokingCredential, setRevokingCredential] = useState<ProviderCredentialDto | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const credentialsByProvider = new Map<string, ProviderCredentialDto>();
  for (const cred of credentials) {
    credentialsByProvider.set(cred.provider_id, cred);
  }

  async function handleSaveSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!configuringProvider || !secret.trim()) return;

    setIsSaving(true);
    setErrorMessage(null);
    try {
      const res = await onSave({
        provider_id: configuringProvider.provider_id,
        secret: secret.trim(),
        reference: reference.trim() || "default",
      });
      if (res.success) {
        setConfiguringProvider(null);
        setSecret("");
        setReference("default");
      } else {
        setErrorMessage(res.error ?? "Failed to save credential.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConfirmRevoke() {
    if (!revokingCredential) return;
    setIsRevoking(true);
    setRevokeError(null);
    try {
      const result = await onRevoke(revokingCredential.credential_id);
      if (result.success) {
        setRevokingCredential(null);
      } else {
        setRevokeError(result.error ?? "Failed to revoke credential.");
      }
    } catch (error) {
      setRevokeError(error instanceof Error ? error.message : "Failed to revoke credential.");
    } finally {
      setIsRevoking(false);
    }
  }

  function closeConfigure() {
    setConfiguringProvider(null);
    setSecret("");
    setErrorMessage(null);
  }

  return (
    <div className="developer-view">
      <p className={`inline-notice ${advancedEnabled ? "inline-notice--success" : "inline-notice--info"}`}>
        {advancedEnabled
          ? "Advanced provider routing enabled: workspace can route across all catalog providers and models."
          : "Standard release chain active: workspace is using standard multi-model routing."}
      </p>
      {!canManage ? <p className="inline-notice inline-notice--info">Your role can review provider readiness but cannot store or revoke credentials.</p> : null}

      {CATEGORIES.map((cat) => {
        const providers = catalog.filter((p) => p.category === cat.key);
        if (providers.length === 0) return null;
        const headingId = `provider-stage-${cat.key}`;

        return (
          <section aria-labelledby={headingId} className="form-panel" key={cat.key}>
            <h2 className="developer-section-title" id={headingId}>{cat.label}</h2>
            <table aria-labelledby={headingId} className="data-table">
              <thead>
                <tr>
                  <th scope="col">Provider</th>
                  <th scope="col">Status</th>
                  <th scope="col">Models</th>
                  <th scope="col">Reference</th>
                  {canManage ? <th scope="col"><span className="sr-only">Actions</span></th> : null}
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => {
                  const cred = credentialsByProvider.get(p.provider_id);
                  const isConfigured = Boolean(cred);

                  return (
                    <tr key={p.provider_id}>
                      <td data-label="Provider"><strong>{providerName(p.provider_id)}</strong></td>
                      <td data-label="Status">
                        <StatusBadge tone={isConfigured ? "success" : "neutral"}>{isConfigured ? "Configured" : "Not configured"}</StatusBadge>
                      </td>
                      <td data-label="Models"><span className="technical-value">{p.models.join(", ") || "—"}</span></td>
                      <td data-label="Reference"><span className="technical-value">{cred ? `${cred.reference} (v${cred.rotation_version})` : "—"}</span></td>
                      {canManage ? (
                        <td className="data-table__actions" data-label="Actions">
                          <button
                            aria-label={`Configure ${p.provider_id}`}
                            className="button button--secondary"
                            onClick={() => {
                              setConfiguringProvider(p);
                              setSecret("");
                              setReference("default");
                              setErrorMessage(null);
                            }}
                            type="button"
                          >
                            Configure
                          </button>
                          {cred ? (
                            <button
                              className="button button--quiet-danger"
                              onClick={() => { setRevokingCredential(cred); setRevokeError(null); }}
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
          </section>
        );
      })}

      {configuringProvider ? (
        <FormDialog
          busy={isSaving}
          description="Secret values are encrypted at rest with envelope encryption and never returned in plaintext."
          error={errorMessage}
          onCancel={closeConfigure}
          onSubmit={(event) => void handleSaveSubmit(event)}
          submitDisabled={!secret.trim()}
          submitLabel="Save credential"
          title={`Configure ${providerName(configuringProvider.provider_id)}`}
        >
          <FormField label="API key or secret" name="cred-secret">
            <input autoComplete="off" onChange={(e) => setSecret(e.target.value)} placeholder="Paste your secret key" required spellCheck={false} type="password" value={secret} />
          </FormField>
          <FormField hint="A label to tell credentials apart, for example default or production." label="Reference label" name="cred-ref">
            <input onChange={(e) => setReference(e.target.value)} placeholder="default" type="text" value={reference} />
          </FormField>
        </FormDialog>
      ) : null}

      {revokingCredential ? (
        <ConfirmDialog
          busy={isRevoking}
          confirmLabel="Confirm revoke"
          error={revokeError}
          onCancel={() => { setRevokingCredential(null); setRevokeError(null); }}
          onConfirm={() => void handleConfirmRevoke()}
          title="Revoke credential"
        >
          <p>
            Are you sure you want to revoke the credential for {providerName(revokingCredential.provider_id)}? Agents configured to use this provider
            will fail over to secondary providers.
          </p>
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
