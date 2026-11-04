"use client";

import { useState } from "react";
import type { TelephonyPolicyDto, TelephonySettingsDto } from "./types";

export interface TelephonyChannelViewProps {
  settings: TelephonySettingsDto;
  canEdit: boolean;
  onSave: (policy: TelephonyPolicyDto) => Promise<{ success: boolean; error?: string }>;
}

export function TelephonyChannelView({ settings, canEdit, onSave }: TelephonyChannelViewProps) {
  const [policy, setPolicy] = useState<TelephonyPolicyDto>(settings.policy);
  const [destinationsInput, setDestinationsInput] = useState<string>(
    settings.policy.allowed_destinations.join(", ")
  );
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const readinessState = settings.readiness.state;
  const isReady = readinessState === "ready";
  const isNotConfigured = readinessState === "not_configured";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;

    setIsSaving(true);
    setStatusMessage(null);

    const parsedDestinations = destinationsInput
      .split(/[,\n]/)
      .map((d) => d.trim())
      .filter((d) => d.length > 0);

    const updated: TelephonyPolicyDto = {
      ...policy,
      allowed_destinations: parsedDestinations,
    };

    const res = await onSave(updated);
    setIsSaving(false);
    if (res.success) {
      setPolicy(updated);
      setStatusMessage("Telephony policy saved successfully.");
    } else {
      setStatusMessage(res.error ?? "Failed to save policy.");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <header>
        <h2>Telephony Voice Channel</h2>
        <p>
          Configure call limits, calling windows, and outbound destination policies for phone calls.
        </p>
      </header>

      <section
        style={{
          border: "1px solid #e4e4e7",
          borderRadius: "8px",
          padding: "1rem",
          background: "#fafafa",
        }}
      >
        <h3>Trunk Readiness</h3>
        <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
          <div>
            <strong>Status: </strong>
            <span
              style={{
                fontWeight: 600,
                color: isReady ? "#16a34a" : isNotConfigured ? "#dc2626" : "#d97706",
              }}
            >
              {isReady ? "Ready" : isNotConfigured ? "Not configured" : "Readiness unknown"}
            </span>
          </div>
          <div>
            <strong>SIP Trunk: </strong>
            {settings.readiness.trunk_configured ? "Configured" : "Unconfigured"}
          </div>
          <div>
            <strong>Telephony Entitlement: </strong>
            {settings.readiness.telephony_entitled ? "Enabled" : "Disabled"}
          </div>
          <div>
            <strong>Carrier Health: </strong>
            {settings.readiness.carrier_health}
          </div>
        </div>

        <div
          style={{
            marginTop: "1rem",
            padding: "0.75rem",
            background: "#fef3c7",
            borderRadius: "6px",
            fontSize: "0.9rem",
            color: "#92400e",
          }}
        >
          <strong>Notice:</strong> Carrier purchase and provisioning is not automated in self-serve
          mode; contact support to attach a dedicated Telnyx SIP trunk.
        </div>
      </section>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h3>Outbound Calling Policy</h3>

        <div>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input
              type="checkbox"
              aria-label="Allow outbound calls"
              checked={policy.outbound_enabled}
              disabled={!canEdit}
              onChange={(e) => setPolicy({ ...policy, outbound_enabled: e.target.checked })}
            />
            Allow outbound calls
          </label>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", maxWidth: "500px" }}>
          <div>
            <label htmlFor="window-start" style={{ display: "block", fontSize: "0.9rem" }}>
              Calling Window Start
            </label>
            <input
              id="window-start"
              type="text"
              value={policy.window_start}
              disabled={!canEdit}
              onChange={(e) => setPolicy({ ...policy, window_start: e.target.value })}
              style={{ width: "100%", padding: "0.5rem" }}
            />
          </div>
          <div>
            <label htmlFor="window-end" style={{ display: "block", fontSize: "0.9rem" }}>
              Calling Window End
            </label>
            <input
              id="window-end"
              type="text"
              value={policy.window_end}
              disabled={!canEdit}
              onChange={(e) => setPolicy({ ...policy, window_end: e.target.value })}
              style={{ width: "100%", padding: "0.5rem" }}
            />
          </div>
        </div>

        <div style={{ maxWidth: "500px" }}>
          <label htmlFor="calling-timezone" style={{ display: "block", fontSize: "0.9rem" }}>
            Calling Timezone
          </label>
          <input
            id="calling-timezone"
            type="text"
            value={policy.calling_timezone}
            disabled={!canEdit}
            onChange={(e) => setPolicy({ ...policy, calling_timezone: e.target.value })}
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        <div style={{ maxWidth: "500px" }}>
          <label htmlFor="max-duration" style={{ display: "block", fontSize: "0.9rem" }}>
            Max Call Duration (seconds)
          </label>
          <input
            id="max-duration"
            type="number"
            value={policy.max_call_duration_seconds}
            disabled={!canEdit}
            onChange={(e) =>
              setPolicy({ ...policy, max_call_duration_seconds: parseInt(e.target.value, 10) || 600 })
            }
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        <div style={{ maxWidth: "500px" }}>
          <label htmlFor="allowed-destinations" style={{ display: "block", fontSize: "0.9rem" }}>
            Allowed Destinations (E.164, comma-separated)
          </label>
          <textarea
            id="allowed-destinations"
            value={destinationsInput}
            disabled={!canEdit}
            onChange={(e) => setDestinationsInput(e.target.value)}
            rows={3}
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        {statusMessage && (
          <div
            style={{
              padding: "0.5rem",
              borderRadius: "4px",
              background: statusMessage.includes("success") ? "#dcfce7" : "#fee2e2",
              color: statusMessage.includes("success") ? "#15803d" : "#b91c1c",
              fontSize: "0.9rem",
            }}
          >
            {statusMessage}
          </div>
        )}

        {canEdit && (
          <div>
            <button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : "Save Policy"}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
