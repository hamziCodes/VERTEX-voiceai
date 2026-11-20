"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { FormField } from "@/components/studio/form-field";
import type { SupportSessionDto } from "@/data/schema";

import { REASON_MAX_LENGTH, REASON_MIN_LENGTH, type EndSupportSessionInput, type SupportActionResult } from "./types";

export function EndSupportSession({
  compact = false,
  onEnd,
  sessionId,
  tenantName,
}: {
  compact?: boolean;
  onEnd(input: EndSupportSessionInput): Promise<SupportActionResult<SupportSessionDto>>;
  sessionId: string;
  tenantName: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    const normalized = reason.split(/\s+/).filter(Boolean).join(" ");
    if (normalized && normalized.length < REASON_MIN_LENGTH) {
      setError(`Leave the reason empty or give at least ${REASON_MIN_LENGTH} characters.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await onEnd({ sessionId, reason: normalized });
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setOpen(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        aria-label={compact ? `End support session for ${tenantName}` : undefined}
        className="button button--secondary"
        onClick={() => { setOpen(true); setError(null); setReason(""); }}
        type="button"
      >
        {compact ? "End" : "End session"}
      </button>
      {open ? (
        <ConfirmDialog
          busy={busy}
          confirmLabel="End session"
          error={error}
          onCancel={() => { if (!busy) setOpen(false); }}
          onConfirm={() => void confirm()}
          title="End support session"
        >
          <p>Access to {tenantName} stops immediately. The session stays in the platform audit.</p>
          <FormField hint={`Optional. ${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters.`} label="Reason for ending" name={`end-reason-${sessionId}`}>
            <textarea maxLength={REASON_MAX_LENGTH} onChange={(event) => setReason(event.target.value)} rows={2} value={reason} />
          </FormField>
        </ConfirmDialog>
      ) : null}
    </>
  );
}
