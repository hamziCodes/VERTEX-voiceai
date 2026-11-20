"use client";

import { useState, type FormEvent } from "react";

import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";

import type { TelephonyPolicyDto, TelephonySettingsDto } from "./types";

export interface TelephonyChannelViewProps {
  settings: TelephonySettingsDto;
  canEdit: boolean;
  onSave: (policy: TelephonyPolicyDto) => Promise<{ success: boolean; error?: string }>;
}

type SaveStatus = { tone: "success" | "danger"; message: string } | null;

export function TelephonyChannelView({ settings, canEdit, onSave }: TelephonyChannelViewProps) {
  const [policy, setPolicy] = useState<TelephonyPolicyDto>(settings.policy);
  const [destinationsInput, setDestinationsInput] = useState<string>(
    settings.policy.allowed_destinations.join(", ")
  );
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<SaveStatus>(null);

  const readinessState = settings.readiness.state;
  const isReady = readinessState === "ready";
  const isNotConfigured = readinessState === "not_configured";

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canEdit) return;

    setIsSaving(true);
    setStatus(null);

    const parsedDestinations = destinationsInput
      .split(/[,\n]/)
      .map((d) => d.trim())
      .filter((d) => d.length > 0);

    const updated: TelephonyPolicyDto = {
      ...policy,
      allowed_destinations: parsedDestinations,
    };

    try {
      const res = await onSave(updated);
      if (res.success) {
        setPolicy(updated);
        setStatus({ tone: "success", message: "Telephony policy saved successfully." });
      } else {
        setStatus({ tone: "danger", message: res.error ?? "Failed to save policy." });
      }
    } catch {
      setStatus({ tone: "danger", message: "Failed to save policy." });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="channel-view">
      <section aria-labelledby="telephony-heading" className="form-panel">
        <div className="panel-heading">
          <p className="screen-eyebrow">Telephony</p>
          <h2 id="telephony-heading">Telephony voice channel</h2>
          <p>Configure call limits, calling windows and outbound destination policy for phone calls.</p>
        </div>
        {!canEdit ? (
          <p className="inline-notice inline-notice--info">Your role can review telephony readiness and policy but cannot change them.</p>
        ) : null}

        <section aria-labelledby="trunk-readiness-heading" className="readiness-list">
          <h3 id="trunk-readiness-heading">Trunk readiness</h3>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>
                <StatusBadge tone={isReady ? "success" : isNotConfigured ? "danger" : "warning"}>
                  {isReady ? "Ready" : isNotConfigured ? "Not configured" : "Readiness unknown"}
                </StatusBadge>
              </dd>
            </div>
            <div>
              <dt>SIP trunk</dt>
              <dd><StatusBadge tone={settings.readiness.trunk_configured ? "success" : "neutral"}>{settings.readiness.trunk_configured ? "Configured" : "Unconfigured"}</StatusBadge></dd>
            </div>
            <div>
              <dt>Telephony entitlement</dt>
              <dd><StatusBadge tone={settings.readiness.telephony_entitled ? "success" : "neutral"}>{settings.readiness.telephony_entitled ? "Enabled" : "Disabled"}</StatusBadge></dd>
            </div>
            <div>
              <dt>Carrier health</dt>
              <dd className="technical-value">{settings.readiness.carrier_health}</dd>
            </div>
          </dl>
        </section>

        <p className="inline-notice inline-notice--warning">
          <strong>Notice:</strong> Carrier purchase and provisioning is not automated in self-serve
          mode; contact support to attach a dedicated Telnyx SIP trunk.
        </p>
      </section>

      <form aria-labelledby="outbound-policy-heading" className="form-panel telephony-policy" onSubmit={handleSubmit}>
        <div className="panel-heading">
          <p className="screen-eyebrow">Policy</p>
          <h3 id="outbound-policy-heading">Outbound calling policy</h3>
          <p>Outbound calls stay limited to these destinations and hours. Saving a policy does not place a call.</p>
        </div>

        <label className="checkbox-row">
          <input
            aria-label="Allow outbound calls"
            checked={policy.outbound_enabled}
            disabled={!canEdit}
            onChange={(e) => setPolicy({ ...policy, outbound_enabled: e.target.checked })}
            type="checkbox"
          />
          <span>Allow outbound calls</span>
        </label>

        <div className="field-grid">
          <FormField hint="24-hour time, for example 09:00:00." label="Calling window start" name="window-start">
            <input disabled={!canEdit} onChange={(e) => setPolicy({ ...policy, window_start: e.target.value })} type="text" value={policy.window_start} />
          </FormField>
          <FormField hint="24-hour time, for example 17:00:00." label="Calling window end" name="window-end">
            <input disabled={!canEdit} onChange={(e) => setPolicy({ ...policy, window_end: e.target.value })} type="text" value={policy.window_end} />
          </FormField>
        </div>

        <div className="field-grid">
          <FormField hint="IANA name, for example Asia/Karachi." label="Calling timezone" name="calling-timezone">
            <input disabled={!canEdit} onChange={(e) => setPolicy({ ...policy, calling_timezone: e.target.value })} type="text" value={policy.calling_timezone} />
          </FormField>
          <FormField label="Max call duration (seconds)" name="max-duration">
            <input
              disabled={!canEdit}
              min={1}
              onChange={(e) => setPolicy({ ...policy, max_call_duration_seconds: parseInt(e.target.value, 10) || 600 })}
              type="number"
              value={policy.max_call_duration_seconds}
            />
          </FormField>
        </div>

        <FormField hint="E.164 numbers separated by commas or new lines, for example +14155550100." label="Allowed destinations" name="allowed-destinations">
          <textarea disabled={!canEdit} onChange={(e) => setDestinationsInput(e.target.value)} rows={3} value={destinationsInput} />
        </FormField>

        {status ? (
          <p className={`inline-notice inline-notice--${status.tone}`} role={status.tone === "success" ? "status" : "alert"}>{status.message}</p>
        ) : null}

        {canEdit ? (
          <div className="panel-actions panel-actions--inline">
            <button className="button button--primary" disabled={isSaving} type="submit">
              {isSaving ? "Saving…" : "Save policy"}
            </button>
          </div>
        ) : null}
      </form>
    </div>
  );
}
