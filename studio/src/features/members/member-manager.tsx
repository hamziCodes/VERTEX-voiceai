"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";

import {
  ADMIN_GRANT_WARNING,
  LAUNCH_ROLES,
  ROLE_DETAILS,
  type ChangeMemberRoleInput,
  type InvitationRevealDto,
  type InviteMemberInput,
  type MemberActionResult,
  type RemoveMemberInput,
  type StudioRole,
  type WorkspaceMemberDto,
} from "./types";

export interface MemberManagerProps {
  members: WorkspaceMemberDto[];
  currentUserId: string;
  workspaceName: string;
  canManage: boolean;
  onInvite(input: InviteMemberInput): Promise<MemberActionResult<InvitationRevealDto>>;
  onChangeRole(input: ChangeMemberRoleInput): Promise<MemberActionResult<WorkspaceMemberDto>>;
  onRemove(input: RemoveMemberInput): Promise<MemberActionResult<null>>;
}

type Feedback = { tone: "success" | "danger"; message: string } | null;
type Reveal = InvitationRevealDto & { url: string };

const ROLE_ORDER = new Map<StudioRole, number>(LAUNCH_ROLES.map((role, index) => [role, index]));
const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown date" : DATE_FORMAT.format(parsed);
}

function memberName(member: WorkspaceMemberDto, currentUserId: string): string {
  return member.user_id === currentUserId ? "You" : `Member ${member.user_id.slice(0, 8)}`;
}

function sortMembers(members: WorkspaceMemberDto[], currentUserId: string): WorkspaceMemberDto[] {
  return [...members].sort((left, right) =>
    (ROLE_ORDER.get(left.role) ?? 99) - (ROLE_ORDER.get(right.role) ?? 99)
    || Number(right.user_id === currentUserId) - Number(left.user_id === currentUserId)
    || left.user_id.localeCompare(right.user_id));
}

function invitationUrl(path: string): string {
  return typeof window === "undefined" ? path : new URL(path, window.location.origin).toString();
}

export function MemberManager({ members, currentUserId, workspaceName, canManage, onInvite, onChangeRole, onRemove }: MemberManagerProps) {
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [draftRoles, setDraftRoles] = useState<Record<string, StudioRole>>({});
  const [pendingMember, setPendingMember] = useState<string | null>(null);
  const [removing, setRemoving] = useState<WorkspaceMemberDto | null>(null);

  const ordered = sortMembers(members, currentUserId);
  const adminCount = members.filter((member) => member.role === "tenant_admin").length;

  async function updateRole(member: WorkspaceMemberDto, role: StudioRole) {
    setPendingMember(member.user_id);
    setFeedback(null);
    try {
      const result = await onChangeRole({ userId: member.user_id, role });
      if (result.ok) {
        setDraftRoles((current) => {
          const next = { ...current };
          delete next[member.user_id];
          return next;
        });
        setFeedback({ tone: "success", message: `Role updated to ${ROLE_DETAILS[role].label}.` });
      } else {
        setFeedback({ tone: "danger", message: result.message });
      }
    } catch {
      setFeedback({ tone: "danger", message: "The role could not be updated. Try again." });
    } finally {
      setPendingMember(null);
    }
  }

  async function confirmRemove(member: WorkspaceMemberDto): Promise<boolean> {
    setPendingMember(member.user_id);
    setFeedback(null);
    try {
      const result = await onRemove({ userId: member.user_id });
      if (result.ok) {
        setFeedback({ tone: "success", message: "Member removed." });
        return true;
      }
      setFeedback({ tone: "danger", message: result.message });
      return false;
    } catch {
      setFeedback({ tone: "danger", message: "The member could not be removed. Try again." });
      return false;
    } finally {
      setPendingMember(null);
    }
  }

  return (
    <div className="member-manager">
      {feedback ? (
        <div className={`inline-notice inline-notice--${feedback.tone === "success" ? "success" : "danger"}`} role={feedback.tone === "success" ? "status" : "alert"}>
          {feedback.message}
        </div>
      ) : null}

      <div className="member-layout">
        <section aria-labelledby="member-list-heading" className="member-panel">
          <div className="member-panel__heading">
            <div>
              <h2 id="member-list-heading">People with access</h2>
              <p>Members are shown by account ID. Names and emails are not shared by the workspace service yet.</p>
            </div>
            <StatusBadge>{`${members.length} ${members.length === 1 ? "member" : "members"}`}</StatusBadge>
          </div>
          {!canManage ? (
            <div className="inline-notice inline-notice--info">Your role can view members but cannot invite, change roles, or remove members.</div>
          ) : null}
          <ul aria-label="Workspace members" className="member-list">
            {ordered.map((member) => {
              const name = memberName(member, currentUserId);
              const isProtected = member.role === "tenant_admin" && adminCount <= 1;
              const draft = draftRoles[member.user_id] ?? member.role;
              const busy = pendingMember === member.user_id;
              const selectId = `member-role-${member.user_id}`;
              return (
                <li aria-label={`${name} · ${ROLE_DETAILS[member.role].label}`} className="member-row" key={member.user_id}>
                  <span aria-hidden="true" className="member-row__mark">{member.user_id === currentUserId ? "Y" : member.user_id.slice(0, 1).toUpperCase()}</span>
                  <div className="member-row__identity">
                    <div className="member-row__title">
                      <strong>{name}</strong>
                      <StatusBadge tone={member.role === "tenant_admin" ? "info" : "neutral"}>{ROLE_DETAILS[member.role].label}</StatusBadge>
                    </div>
                    <span className="technical-value" title={member.user_id}>{member.user_id}</span>
                    <span className="member-row__meta">Joined {formatDate(member.created_at)}</span>
                    {canManage && isProtected ? (
                      <span className="member-row__reason">Last administrator. Promote another member before changing or removing this role.</span>
                    ) : null}
                  </div>
                  {canManage ? (
                    <div className="member-row__controls">
                      <div className="member-row__role">
                        <label className="sr-only" htmlFor={selectId}>{`Role for ${name}`}</label>
                        <select
                          disabled={isProtected || busy}
                          id={selectId}
                          onChange={(event) => setDraftRoles((current) => ({ ...current, [member.user_id]: event.target.value as StudioRole }))}
                          value={draft}
                        >
                          {LAUNCH_ROLES.map((role) => <option key={role} value={role}>{ROLE_DETAILS[role].label}</option>)}
                        </select>
                        <button
                          aria-label={`Update role for ${name}`}
                          className="button button--secondary"
                          disabled={isProtected || busy || draft === member.role}
                          onClick={() => void updateRole(member, draft)}
                          type="button"
                        >
                          {busy ? "Saving…" : "Update role"}
                        </button>
                      </div>
                      <button
                        aria-label={`Remove ${name}`}
                        className="button button--quiet-danger"
                        disabled={isProtected || busy}
                        onClick={() => { setFeedback(null); setRemoving(member); }}
                        type="button"
                      >
                        Remove
                      </button>
                      {draft === "tenant_admin" && member.role !== "tenant_admin" ? (
                        <p className="inline-notice inline-notice--warning member-row__warning" role="note">{ADMIN_GRANT_WARNING}</p>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>

        {canManage ? <InvitationPanel onInvite={onInvite} /> : null}
      </div>

      {removing ? (
        <RemoveMemberDialog
          busy={pendingMember === removing.user_id}
          memberName={memberName(removing, currentUserId)}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            if (await confirmRemove(removing)) setRemoving(null);
          }}
          workspaceName={workspaceName}
        />
      ) : null}
    </div>
  );
}

function InvitationPanel({ onInvite }: { onInvite: MemberManagerProps["onInvite"] }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StudioRole>("tenant_viewer");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [copyState, setCopyState] = useState<string | null>(null);
  const headingId = useId();
  const revealHeadingId = useId();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setReveal(null);
    try {
      const result = await onInvite({ email: email.trim(), role });
      if (result.ok) {
        setReveal({ ...result.data, url: invitationUrl(result.data.invitationPath) });
        setCopyState(null);
        setEmail("");
        setRole("tenant_viewer");
      } else {
        setError(result.message);
      }
    } catch {
      setError("The invitation could not be created. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function copyLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopyState("Link copied. It will not be shown again after you close this panel.");
    } catch {
      setCopyState("Copy is unavailable here. Select the link and copy it manually.");
    }
  }

  return (
    <div className="member-side">
      {reveal ? (
        <section aria-labelledby={revealHeadingId} className="member-panel invitation-reveal">
          <StatusBadge tone="warning">Shown once</StatusBadge>
          <h2 id={revealHeadingId}>{`Invitation link for ${reveal.email}`}</h2>
          <p>
            Copy this link now and send it privately. It is shown once, works only for {reveal.email} as {ROLE_DETAILS[reveal.role].label},
            and expires {formatDate(reveal.expiresAt)}. Studio does not store it in this browser.
          </p>
          <div className="form-field">
            <label htmlFor="invitation-link">Invitation link</label>
            <input id="invitation-link" onFocus={(event) => event.currentTarget.select()} readOnly spellCheck={false} value={reveal.url} />
          </div>
          {copyState ? <p className="member-panel__hint" role="status">{copyState}</p> : null}
          <div className="member-panel__actions">
            <button className="button button--secondary" onClick={() => void copyLink(reveal.url)} type="button">Copy link</button>
            <button className="button button--primary" onClick={() => { setReveal(null); setCopyState(null); }} type="button">Done</button>
          </div>
        </section>
      ) : null}

      <form aria-labelledby={headingId} className="member-panel invite-form" noValidate onSubmit={(event) => void submit(event)}>
        <div>
          <h2 id={headingId}>Invite a member</h2>
          <p>The invitation link works once, for the invited email address only.</p>
        </div>
        <FormField hint="Use the address they will sign in with." label="Email address" name="invite-email">
          <input autoComplete="off" inputMode="email" maxLength={320} onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
        </FormField>
        <fieldset className="choice-grid role-choice-grid">
          <legend>Role</legend>
          {LAUNCH_ROLES.map((option) => (
            <label className="choice-card" key={option}>
              <input checked={role === option} name="invite-role" onChange={() => setRole(option)} type="radio" value={option} />
              <span className="choice-card__copy">
                <strong>{ROLE_DETAILS[option].label}</strong>
                <span>{ROLE_DETAILS[option].description}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {role === "tenant_admin" ? <p className="inline-notice inline-notice--warning" role="note">{ADMIN_GRANT_WARNING}</p> : null}
        {error ? <p className="inline-notice inline-notice--danger" role="alert">{error}</p> : null}
        <button className="button button--primary" disabled={submitting || !email.trim()} type="submit">
          {submitting ? "Creating invitation…" : "Create invitation"}
        </button>
      </form>
    </div>
  );
}

function RemoveMemberDialog({ busy, memberName, onCancel, onConfirm, workspaceName }: {
  busy: boolean;
  memberName: string;
  onCancel(): void;
  onConfirm(): Promise<void>;
  workspaceName: string;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape" && !busy) onCancel(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previous?.focus?.();
    };
  }, [busy, onCancel]);

  return (
    <div className="studio-dialog-backdrop">
      <div aria-labelledby={titleId} aria-modal="true" className="studio-dialog" role="dialog">
        <h2 id={titleId}>Remove member</h2>
        <p>
          Remove <strong>{memberName}</strong>? They lose access to {workspaceName} immediately. To restore access later, send a new invitation.
        </p>
        <div className="member-panel__actions">
          <button className="button button--secondary" disabled={busy} onClick={onCancel} ref={cancelRef} type="button">Cancel</button>
          <button className="button button--danger" disabled={busy} onClick={() => void onConfirm()} type="button">
            {busy ? "Removing…" : "Remove member"}
          </button>
        </div>
      </div>
    </div>
  );
}
