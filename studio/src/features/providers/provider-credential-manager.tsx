"use client";

import { useState } from "react";
import type { CatalogProviderDto, ProviderCredentialDto, StoreCredentialInput } from "./types";

export interface ProviderCredentialManagerProps {
  catalog: CatalogProviderDto[];
  credentials: ProviderCredentialDto[];
  advancedEnabled: boolean;
  canManage: boolean;
  onSave: (input: StoreCredentialInput) => Promise<{ success: boolean; error?: string }>;
  onRevoke: (credentialId: string) => Promise<{ success: boolean; error?: string }>;
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

  const categories = [
    { key: "stt", label: "Speech-to-Text (STT)" },
    { key: "llm", label: "Large Language Models (LLM)" },
    { key: "tts", label: "Text-to-Speech (TTS)" },
  ];

  async function handleSaveSubmit(e: React.FormEvent) {
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <header>
        <h2>AI Provider Credentials</h2>
        <p>Manage encrypted provider API keys (BYOK) for voice pipeline orchestration.</p>
      </header>

      <div
        style={{
          padding: "0.75rem 1rem",
          borderRadius: "6px",
          background: advancedEnabled ? "#ecfdf5" : "#f4f4f5",
          border: `1px solid ${advancedEnabled ? "#a7f3d0" : "#e4e4e7"}`,
          fontSize: "0.9rem",
          color: advancedEnabled ? "#065f46" : "#3f3f46",
        }}
      >
        {advancedEnabled
          ? "Advanced provider routing enabled: workspace can route across all catalog providers and models."
          : "Standard release chain active: workspace is using standard multi-model routing."}
      </div>

      {categories.map((cat) => {
        const providers = catalog.filter((p) => p.category === cat.key);
        if (providers.length === 0) return null;

        return (
          <section key={cat.key} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <h3>{cat.label}</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e4e4e7" }}>
                  <th style={{ padding: "0.5rem" }}>Provider</th>
                  <th style={{ padding: "0.5rem" }}>Status</th>
                  <th style={{ padding: "0.5rem" }}>Models</th>
                  <th style={{ padding: "0.5rem" }}>Reference</th>
                  {canManage && <th style={{ padding: "0.5rem" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => {
                  const cred = credentialsByProvider.get(p.provider_id);
                  const isConfigured = Boolean(cred);

                  return (
                    <tr key={p.provider_id} style={{ borderBottom: "1px solid #f4f4f5" }}>
                      <td style={{ padding: "0.75rem 0.5rem", fontWeight: 600 }}>
                        {p.provider_id.toUpperCase()}
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem" }}>
                        <span
                          style={{
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            background: isConfigured ? "#dcfce7" : "#f4f4f5",
                            color: isConfigured ? "#166534" : "#71717a",
                          }}
                        >
                          {isConfigured ? "Configured" : "Not configured"}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem", fontSize: "0.85rem", color: "#666" }}>
                        {p.models.join(", ") || "-"}
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem", fontSize: "0.85rem", color: "#666" }}>
                        {cred ? `${cred.reference} (v${cred.rotation_version})` : "-"}
                      </td>
                      {canManage && (
                        <td style={{ padding: "0.75rem 0.5rem" }}>
                          <button
                            type="button"
                            aria-label={`Configure ${p.provider_id}`}
                            onClick={() => {
                              setConfiguringProvider(p);
                              setSecret("");
                              setReference("default");
                              setErrorMessage(null);
                            }}
                            style={{ marginRight: "0.5rem" }}
                          >
                            Configure
                          </button>
                          {cred && (
                            <button
                              type="button"
                              onClick={() => {
                                setRevokingCredential(cred);
                                setRevokeError(null);
                              }}
                              style={{ color: "#dc2626", background: "none", border: "none", cursor: "pointer" }}
                            >
                              Revoke
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        );
      })}

      {/* Configure Credential Dialog */}
      {configuringProvider && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
        >
          <div style={{ background: "#fff", padding: "1.5rem", borderRadius: "8px", width: "440px" }}>
            <h3>Configure {configuringProvider.provider_id.toUpperCase()}</h3>
            <p style={{ fontSize: "0.85rem", color: "#666", margin: "0.5rem 0 1rem 0" }}>
              Secret values are encrypted at rest with envelope encryption and never returned in plaintext.
            </p>
            <form onSubmit={handleSaveSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label htmlFor="cred-secret" style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                  API Key or Secret
                </label>
                <input
                  id="cred-secret"
                  type="password"
                  autoComplete="off"
                  required
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem" }}
                  placeholder="Paste your secret key"
                />
              </div>

              <div>
                <label htmlFor="cred-ref" style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                  Reference Label
                </label>
                <input
                  id="cred-ref"
                  type="text"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem" }}
                  placeholder="default"
                />
              </div>

              {errorMessage && <div style={{ color: "#dc2626", fontSize: "0.85rem" }}>{errorMessage}</div>}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button type="button" onClick={() => setConfiguringProvider(null)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save Credential"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Revoke Confirmation Dialog */}
      {revokingCredential && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
        >
          <div style={{ background: "#fff", padding: "1.5rem", borderRadius: "8px", width: "420px" }}>
            <h3 style={{ color: "#dc2626" }}>Revoke Credential</h3>
            <p style={{ fontSize: "0.9rem", color: "#4b5563", margin: "1rem 0" }}>
              Are you sure you want to revoke the credential for{" "}
              <strong>{revokingCredential.provider_id.toUpperCase()}</strong>? Agents configured to use this provider
              will failover to secondary providers.
            </p>
            {revokeError && <p role="alert" style={{ color: "#dc2626" }}>{revokeError}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" disabled={isRevoking} onClick={() => {
                setRevokingCredential(null);
                setRevokeError(null);
              }}>
                Cancel
              </button>
              <button
                type="button"
                disabled={isRevoking}
                onClick={handleConfirmRevoke}
                style={{ background: "#dc2626", color: "#fff" }}
              >
                {isRevoking ? "Revoking..." : "Confirm Revoke"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
