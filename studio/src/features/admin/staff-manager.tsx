"use client";

import { useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { FormDialog } from "@/components/studio/form-dialog";
import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";
import { formatDate } from "@/lib/format";

import {
  PLATFORM_ROLE_DETAILS,
  PLATFORM_ROLES,
  REASON_MAX_LENGTH,
  REASON_MIN_LENGTH,
  type GrantStaffRoleInput,
  type PlatformRole,
  type PlatformStaffMemberDto,
  type RevokeStaffRoleInput,
  type StaffActionResult,
} from "./types";

export interface StaffManagerProps {
  staff: PlatformStaffMemberDto[];
  currentUserId: string;
  canManage: boolean;
  onGrant(input: GrantStaffRoleInput): Promise<StaffActionResult<PlatformStaffMemberDto>>;
  onRevoke(input: RevokeStaffRoleInput): Promise<StaffActionResult<null>>;
}

type Dialog =
  | { kind: "grant" }
  | { kind: "change"; member: PlatformStaffMemberDto }
  | { kind: "revoke"; member: PlatformStaffMemberDto }
  | null;

const REASON_HINT = `${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters. Recorded in the platform audit.`;

function normalizeReason(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

function reasonIsValid(value: string): boolean {
  const length = normalizeReason(value).length;
  return length >= REASON_MIN_LENGTH && length <= REASON_MAX_LENGTH;
}

function sortStaff(staff: PlatformStaffMemberDto[]): PlatformStaffMemberDto[] {
  const order = new Map<PlatformRole, number>(PLATFORM_ROLES.map((role, index) => [role, index]));
  return [...staff].sort((a, b) => (order.get(a.role) ?? 9) - (order.get(b.role) ?? 9) || (a.email ?? "").localeCompare(b.email ?? ""));
}

function RoleSelect({ value, onChange }: { value: PlatformRole; onChange(role: PlatformRole): void }) {
  return (
    <FormField hint={PLATFORM_ROLE_DETAILS[value].description} label="Platform role" name="role">
      <select onChange={(event) => onChange(event.target.value as PlatformRole)} value={value}>
        {PLATFORM_ROLES.map((role) => <option key={role} value={role}>{PLATFORM_ROLE_DETAILS[role].label}</option>)}
      </select>
    </FormField>
  );
}

function ReasonField({ value, onChange }: { value: string; onChange(value: string): void }) {
  return (
    <FormField hint={REASON_HINT} label="Reason" name="reason">
      <textarea maxLength={REASON_MAX_LENGTH} onChange={(event) => onChange(event.target.value)} rows={3} value={value} />
    </FormField>
  );
}

export function StaffManager({ staff: initialStaff, currentUserId, canManage, onGrant, onRevoke }: StaffManagerProps) {
  const [staff, setStaff] = useState(() => sortStaff(initialStaff));
  const [dialog, setDialog] = useState<Dialog>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<PlatformRole>("platform_support");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const adminCount = staff.filter((member) => member.role === "platform_admin").length;

  function open(next: Exclude<Dialog, null>) {
    setDialog(next);
    setError(null);
    setReason("");
    setEmail("");
    setRole(next.kind === "change" ? next.member.role : "platform_support");
  }

  function close() {
    if (busy) return;
    setDialog(null);
    setError(null);
  }

  function upsert(member: PlatformStaffMemberDto) {
    setStaff((current) => sortStaff([...current.filter((item) => item.user_id !== member.user_id), member]));
  }

  async function submitGrant(targetEmail: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await onGrant({ email: targetEmail, role, reason: normalizeReason(reason) });
      if (!result.ok) {
        setError(result.message);
        return;
      }
      upsert(result.data);
      setFeedback(`${result.data.email ?? "The staff member"} now has ${PLATFORM_ROLE_DETAILS[result.data.role].label}.`);
      setDialog(null);
    } finally {
      setBusy(false);
    }
  }

  async function confirmRevoke(member: PlatformStaffMemberDto) {
    if (!reasonIsValid(reason)) {
      setError(`Give a reason of at least ${REASON_MIN_LENGTH} characters.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await onRevoke({ userId: member.user_id, reason: normalizeReason(reason) });
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setStaff((current) => current.filter((item) => item.user_id !== member.user_id));
      setFeedback(`Revoked the platform role for ${member.email ?? "this staff member"}.`);
      setDialog(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-staff">
      {feedback ? <p className="inline-notice inline-notice--success" role="status">{feedback}</p> : null}
      {!canManage ? (
        <p className="inline-notice inline-notice--info">Your platform role can view staff but not change roles.</p>
      ) : null}

      <section aria-labelledby="platform-staff-heading" className="form-panel operate-panel">
        <div className="operate-panel__heading">
          <h2 className="operate-panel__title" id="platform-staff-heading">Platform staff</h2>
          {canManage ? <button className="button button--primary" onClick={() => open({ kind: "grant" })} type="button">Grant a role</button> : null}
        </div>
        <p className="muted-copy admin-staff__note">
          A person must sign in to Wavia once before a role can be granted. Platform roles never open customer workspaces.
        </p>
        <table aria-label="Platform staff" className="data-table">
          <thead>
            <tr>
              <th scope="col">Person</th>
              <th scope="col">Role</th>
              <th scope="col">Granted</th>
              <th scope="col">Reason</th>
              {canManage ? <th scope="col"><span className="sr-only">Actions</span></th> : null}
            </tr>
          </thead>
          <tbody>
            {staff.map((member) => {
              const isSelf = member.user_id === currentUserId;
              const lastAdmin = member.role === "platform_admin" && adminCount <= 1;
              const label = member.email ?? "Unknown email";
              return (
                <tr key={member.user_id}>
                  <td data-label="Person">
                    <span className="admin-staff__person">
                      <strong>{label}</strong>
                      {isSelf ? <span className="admin-staff__you">You</span> : null}
                    </span>
                    {lastAdmin && canManage ? <span className="muted-copy admin-staff__hint">Last platform administrator.</span> : null}
                  </td>
                  <td data-label="Role">
                    <StatusBadge tone={member.role === "platform_admin" ? "info" : "neutral"}>{PLATFORM_ROLE_DETAILS[member.role].label}</StatusBadge>
                  </td>
                  <td data-label="Granted"><span className="technical-value">{formatDate(member.granted_at)}</span></td>
                  <td data-label="Reason"><span className="admin-staff__reason">{member.reason}</span></td>
                  {canManage ? (
                    <td className="data-table__actions" data-label="Actions">
                      <button
                        aria-label={`Change role for ${label}`}
                        className="button button--secondary"
                        disabled={lastAdmin || member.email === null}
                        onClick={() => open({ kind: "change", member })}
                        type="button"
                      >
                        Change role
                      </button>
                      <button
                        aria-label={`Revoke ${label}`}
                        className="button button--secondary"
                        disabled={lastAdmin}
                        onClick={() => open({ kind: "revoke", member })}
                        type="button"
                      >
                        Revoke
                      </button>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {dialog?.kind === "grant" ? (
        <FormDialog
          busy={busy}
          description="The person keeps any customer workspace memberships they already have; this role adds internal access only."
          error={error}
          onCancel={close}
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            void submitGrant(email.trim().toLowerCase());
          }}
          submitDisabled={!email.trim() || !reasonIsValid(reason)}
          submitLabel="Grant role"
          title="Grant a platform role"
        >
          <FormField label="Email address" name="email">
            <input autoComplete="off" maxLength={320} onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
          </FormField>
          <RoleSelect onChange={setRole} value={role} />
          <ReasonField onChange={setReason} value={reason} />
        </FormDialog>
      ) : null}

      {dialog?.kind === "change" ? (
        <FormDialog
          busy={busy}
          description={`Change the platform role for ${dialog.member.email ?? "this staff member"}.`}
          error={error}
          onCancel={close}
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            if (dialog.member.email) void submitGrant(dialog.member.email);
          }}
          submitDisabled={role === dialog.member.role || !reasonIsValid(reason)}
          submitLabel="Change role"
          title="Change platform role"
        >
          <RoleSelect onChange={setRole} value={role} />
          <ReasonField onChange={setReason} value={reason} />
        </FormDialog>
      ) : null}

      {dialog?.kind === "revoke" ? (
        <ConfirmDialog
          busy={busy}
          confirmLabel="Revoke role"
          error={error}
          onCancel={close}
          onConfirm={() => void confirmRevoke(dialog.member)}
          title="Revoke platform role"
        >
          <p>
            {dialog.member.email ?? "This staff member"} loses {PLATFORM_ROLE_DETAILS[dialog.member.role].label} access immediately.
            Customer workspace memberships are not affected.
          </p>
          <ReasonField onChange={setReason} value={reason} />
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
