"use client";

import { useState } from "react";
import type { APIKeyDto, CreateApiKeyResponseDto } from "@/data/schema";
import type { CreateAPIKeyInput } from "./types";

export interface APIKeyManagerProps {
  keys: APIKeyDto[];
  canManage: boolean;
  onCreate: (input: CreateAPIKeyInput) => Promise<CreateApiKeyResponseDto>;
  onRevoke: (keyId: string) => Promise<{ success: boolean; error?: string }>;
}

export function APIKeyManager({ keys, canManage, onCreate, onRevoke }: APIKeyManagerProps) {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createdResult, setCreatedResult] = useState<CreateApiKeyResponseDto | null>(null);
  const [hasCopied, setHasCopied] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);

  const [name, setName] = useState("");
  const [role, setRole] = useState<"tenant_viewer" | "tenant_editor">("tenant_viewer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [revokingKey, setRevokingKey] = useState<APIKeyDto | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  async function handleCreateSubmit(e: React.FormEvent) {
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
      setHasCopied(false);
      setAcknowledged(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create key.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCopyKey(secret: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(secret);
      setHasCopied(true);
    }
  }

  function handleCloseReveal() {
    if (!acknowledged) return;
    setCreatedResult(null);
    setHasCopied(false);
    setAcknowledged(false);
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
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2>API Keys</h2>
          <p>Manage API keys for server-side token minting and backend SDK integration.</p>
        </div>
        {canManage && (
          <button type="button" onClick={() => setIsCreateOpen(true)}>
            Create API Key
          </button>
        )}
      </header>

      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e4e4e7" }}>
            <th style={{ padding: "0.75rem 0.5rem" }}>Name</th>
            <th style={{ padding: "0.75rem 0.5rem" }}>Key Prefix</th>
            <th style={{ padding: "0.75rem 0.5rem" }}>Role</th>
            <th style={{ padding: "0.75rem 0.5rem" }}>Scopes</th>
            <th style={{ padding: "0.75rem 0.5rem" }}>Created</th>
            <th style={{ padding: "0.75rem 0.5rem" }}>Status</th>
            {canManage && <th style={{ padding: "0.75rem 0.5rem" }}>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const isRevoked = Boolean(k.revoked_at);
            const isExpired = Boolean(k.expires_at && new Date(k.expires_at) < new Date());
            const statusLabel = isRevoked ? "Revoked" : isExpired ? "Expired" : "Active";

            return (
              <tr key={k.key_id} style={{ borderBottom: "1px solid #f4f4f5" }}>
                <td style={{ padding: "0.75rem 0.5rem", fontWeight: 500 }}>{k.name}</td>
                <td style={{ padding: "0.75rem 0.5rem", fontFamily: "monospace" }}>
                  {k.key_prefix}...
                </td>
                <td style={{ padding: "0.75rem 0.5rem" }}>{k.role}</td>
                <td style={{ padding: "0.75rem 0.5rem" }}>
                  {k.scopes.map((s) => (
                    <code key={s} style={{ marginRight: "0.25rem" }}>
                      {s}
                    </code>
                  ))}
                </td>
                <td style={{ padding: "0.75rem 0.5rem", color: "#666" }}>
                  {k.created_at ? new Date(k.created_at).toLocaleDateString() : "-"}
                </td>
                <td style={{ padding: "0.75rem 0.5rem" }}>
                  <span
                    style={{
                      padding: "0.2rem 0.5rem",
                      borderRadius: "4px",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      background: isRevoked || isExpired ? "#fee2e2" : "#dcfce7",
                      color: isRevoked || isExpired ? "#991b1b" : "#166534",
                    }}
                  >
                    {statusLabel}
                  </span>
                </td>
                {canManage && (
                  <td style={{ padding: "0.75rem 0.5rem" }}>
                    {!isRevoked && !isExpired && (
                      <button
                        type="button"
                        onClick={() => {
                          setRevokingKey(k);
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
          {keys.length === 0 && (
            <tr>
              <td colSpan={canManage ? 7 : 6} style={{ padding: "1.5rem", textAlign: "center", color: "#888" }}>
                No API keys created yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Create Dialog */}
      {isCreateOpen && (
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
            <h3>Create API Key</h3>
            <form onSubmit={handleCreateSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
              <div>
                <label htmlFor="key-name" style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                  Key Name
                </label>
                <input
                  id="key-name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem" }}
                  placeholder="e.g. Production Web Client"
                />
              </div>

              <div>
                <label htmlFor="key-role" style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                  Role
                </label>
                <select
                  id="key-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value as "tenant_viewer" | "tenant_editor")}
                  style={{ width: "100%", padding: "0.5rem" }}
                >
                  <option value="tenant_viewer">tenant_viewer (minting & read access)</option>
                  <option value="tenant_editor">tenant_editor (minting & editor access)</option>
                </select>
              </div>

              {formError && <div style={{ color: "#dc2626", fontSize: "0.85rem" }}>{formError}</div>}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button type="button" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Generating..." : "Generate Key"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* One-Time Reveal Modal */}
      {createdResult && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
          }}
        >
          <div style={{ background: "#fff", padding: "1.5rem", borderRadius: "8px", width: "480px" }}>
            <h3 style={{ color: "#b45309" }}>Save this secret key now</h3>
            <p style={{ fontSize: "0.9rem", color: "#4b5563" }}>
              You will not be able to see it again. Copy and store it safely in your environment variables.
            </p>

            <div
              style={{
                background: "#f4f4f5",
                padding: "0.75rem",
                borderRadius: "4px",
                fontFamily: "monospace",
                wordBreak: "break-all",
                margin: "1rem 0",
              }}
            >
              {createdResult.api_key}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <button type="button" onClick={() => handleCopyKey(createdResult.api_key)}>
                {hasCopied ? "Copied!" : "Copy to Clipboard"}
              </button>
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  aria-label="I have copied this secret key"
                  checked={acknowledged}
                  onChange={(e) => setAcknowledged(e.target.checked)}
                />
                I have copied this secret key
              </label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button type="button" disabled={!acknowledged} onClick={handleCloseReveal}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Revoke Confirmation Dialog */}
      {revokingKey && (
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
            <h3 style={{ color: "#dc2626" }}>Revoke API Key</h3>
            <p style={{ fontSize: "0.9rem", color: "#4b5563", margin: "1rem 0" }}>
              Are you sure you want to revoke <strong>{revokingKey.name}</strong>? Any services using this key will immediately lose access.
            </p>
            {revokeError && <p role="alert" style={{ color: "#dc2626" }}>{revokeError}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" disabled={isRevoking} onClick={() => {
                setRevokingKey(null);
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
