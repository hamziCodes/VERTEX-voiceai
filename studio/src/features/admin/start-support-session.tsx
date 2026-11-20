"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormDialog } from "@/components/studio/form-dialog";
import { FormField } from "@/components/studio/form-field";
import type { SupportSessionDto } from "@/data/schema";

import {
  REASON_MAX_LENGTH,
  REASON_MIN_LENGTH,
  SUPPORT_DURATIONS,
  SUPPORT_SCOPE_DETAILS,
  SUPPORT_SCOPES,
  type StartSupportSessionInput,
  type SupportActionResult,
  type SupportScope,
} from "./types";

function normalize(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

export function StartSupportSession({
  onStart,
  tenantId,
  tenantName,
}: {
  onStart(input: StartSupportSessionInput): Promise<SupportActionResult<SupportSessionDto>>;
  tenantId: string;
  tenantName: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [scopes, setScopes] = useState<SupportScope[]>(["configuration"]);
  const [duration, setDuration] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonLength = normalize(reason).length;
  const valid = reasonLength >= REASON_MIN_LENGTH && reasonLength <= REASON_MAX_LENGTH && scopes.length > 0;

  function toggle(scope: SupportScope) {
    setScopes((current) => (current.includes(scope) ? current.filter((item) => item !== scope) : SUPPORT_SCOPES.filter((item) => item === scope || current.includes(item))));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await onStart({ tenantId, reason: normalize(reason), reference: reference.trim(), scopes, durationMinutes: duration });
      if (!result.ok) {
        setError(result.message);
        return;
      }
      router.push(`/admin/support-sessions/${result.data.session_id}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="button button--primary" onClick={() => { setOpen(true); setError(null); }} type="button">Start support session</button>
      {open ? (
        <FormDialog
          busy={busy}
          description={`Read-only access to ${tenantName}. It expires automatically, only you can use it, and every view is recorded in the platform audit.`}
          error={error}
          onCancel={() => { if (!busy) setOpen(false); }}
          onSubmit={(event) => void submit(event)}
          submitDisabled={!valid}
          submitLabel="Start session"
          title="Start a support session"
        >
          <FormField hint={`${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters. Recorded in the platform audit.`} label="Reason" name="support-reason">
            <textarea maxLength={REASON_MAX_LENGTH} onChange={(event) => setReason(event.target.value)} rows={3} value={reason} />
          </FormField>
          <FormField label="Ticket reference (optional)" name="support-reference">
            <input maxLength={64} onChange={(event) => setReference(event.target.value)} type="text" value={reference} />
          </FormField>
          <fieldset className="choice-grid support-scopes">
            <legend className="choice-grid__legend">Read scopes</legend>
            {SUPPORT_SCOPES.map((scope) => (
              <label className="support-scope" key={scope}>
                <input checked={scopes.includes(scope)} onChange={() => toggle(scope)} type="checkbox" />
                <span>
                  <strong>{SUPPORT_SCOPE_DETAILS[scope].label}</strong>
                  <span className="muted-copy">{SUPPORT_SCOPE_DETAILS[scope].description}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <FormField label="Duration" name="support-duration">
            <select onChange={(event) => setDuration(Number(event.target.value))} value={String(duration)}>
              {SUPPORT_DURATIONS.map((minutes) => <option key={minutes} value={minutes}>{minutes} minutes</option>)}
            </select>
          </FormField>
        </FormDialog>
      ) : null}
    </>
  );
}
