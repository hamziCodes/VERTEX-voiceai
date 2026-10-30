"use client";

import { useEffect, useState } from "react";

import type { AgentDto, AgentEditorActions, AgentVersionDto, ValidationResultDto } from "./types";

type SaveStatus = "idle" | "saving" | "saved" | "conflict" | "error";

export function AgentDraftEditor({
  initialAgent,
  initialValidation,
  versions,
  canEdit,
  actions,
}: {
  initialAgent: AgentDto;
  initialValidation: ValidationResultDto;
  versions: AgentVersionDto[];
  canEdit: boolean;
  actions: AgentEditorActions;
}) {
  const [draft, setDraft] = useState(initialAgent);
  const [revision, setRevision] = useState(initialAgent.draft_revision);
  const [dirty, setDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [message, setMessage] = useState("");
  const [validation, setValidation] = useState<ValidationResultDto>(initialValidation);
  const [publishedVersion, setPublishedVersion] = useState<number | null>(null);
  const [restoreMessage, setRestoreMessage] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (!dirty || !canEdit || saveStatus === "conflict" || saveStatus === "error") return;
    const timer = window.setTimeout(async () => {
      const result = await actions.saveDraft(initialAgent.agent_id, revision, {
        name: draft.name,
        description: draft.description,
        languages: draft.languages,
        persona: draft.persona,
      });
      if (result.state === "saved") {
        setDraft(result.agent);
        setRevision(result.agent.draft_revision);
        setDirty(false);
        setSaveStatus("saved");
      } else {
        setMessage(result.message);
        setSaveStatus(result.state);
      }
    }, 700);
    return () => window.clearTimeout(timer);
  }, [actions, canEdit, dirty, draft, initialAgent.agent_id, revision, saveStatus]);

  function update(patch: Partial<AgentDto>) {
    setDraft((current) => ({ ...current, ...patch }));
    setValidation({ is_valid: false, errors: [] });
    setDirty(true);
    setSaveStatus("saving");
    setMessage("");
  }

  async function validate() {
    const result = await actions.validateDraft(initialAgent.agent_id);
    setValidation(result);
  }

  async function publish() {
    const result = await actions.publishDraft(initialAgent.agent_id, revision);
    if (result.state === "published") {
      setDraft(result.agent);
      setRevision(result.agent.draft_revision);
      setPublishedVersion(result.version);
      setDirty(false);
      setSaveStatus("saved");
    } else {
      setMessage(result.message);
      setSaveStatus(result.state);
    }
  }

  async function restore(version: number) {
    const result = await actions.restoreVersion(initialAgent.agent_id, version, revision);
    if (result.state === "restored") {
      setDraft(result.agent);
      setRevision(result.agent.draft_revision);
      setDirty(false);
      setValidation({ is_valid: false, errors: [] });
      setSaveStatus("saved");
      setRestoreMessage(`Version ${version} remains immutable; its snapshot was copied into a new draft.`);
    } else {
      setMessage(result.message);
      setSaveStatus(result.state);
    }
  }

  const publishBlocked = !canEdit || dirty || saveStatus === "saving" || saveStatus === "conflict" || !validation.is_valid;

  return (
    <section>
      {!canEdit ? <p>You have view-only access.</p> : null}
      <p aria-live="polite">
        {saveStatus === "saving" ? "Saving…" : null}
        {saveStatus === "saved" ? `Saved at revision ${revision}.` : null}
      </p>
      {saveStatus === "conflict" || saveStatus === "error" ? (
        <div role="alert"><p>{message}</p>{saveStatus === "conflict" ? <button onClick={() => window.location.reload()} type="button">Reload latest draft</button> : null}</div>
      ) : null}
      <label>Agent name<input disabled={!canEdit} value={draft.name} onChange={(event) => update({ name: event.target.value })} /></label>
      <label>Description<textarea disabled={!canEdit} value={draft.description} onChange={(event) => update({ description: event.target.value })} /></label>
      <label>Languages<input disabled={!canEdit} value={draft.languages.join(", ")} onChange={(event) => update({ languages: event.target.value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean) })} /></label>
      <label>Greeting<input disabled={!canEdit} value={draft.persona.greeting ?? ""} onChange={(event) => update({ persona: { ...draft.persona, greeting: event.target.value || null } })} /></label>
      <label>Voice<input disabled={!canEdit} value={draft.persona.voice_id} onChange={(event) => update({ persona: { ...draft.persona, voice_id: event.target.value } })} /></label>
      <section aria-label="Advanced settings">
        <button aria-expanded={advancedOpen} onClick={() => setAdvancedOpen((open) => !open)} type="button">Advanced</button>
        {advancedOpen ? (
          <div>
            <label>System prompt<textarea disabled={!canEdit} value={draft.persona.system_prompt} onChange={(event) => update({ persona: { ...draft.persona, system_prompt: event.target.value } })} /></label>
            <p>Provider routing is preserved from the selected template. Provider selection controls arrive in the channels phase.</p>
          </div>
        ) : null}
      </section>
      <section aria-label="Readiness">
        <h2>Publish readiness</h2>
        {validation.is_valid ? <p>Ready to publish.</p> : <ul>{validation.errors.map((issue) => <li key={`${issue.code}:${issue.field ?? "root"}`}>{issue.message}</li>)}</ul>}
        <button disabled={!canEdit || dirty || saveStatus === "saving" || saveStatus === "conflict"} onClick={validate} type="button">Check readiness</button>
        <button disabled={publishBlocked} onClick={publish} type="button">Publish agent</button>
        {publishedVersion ? <p>Published version {publishedVersion}.</p> : null}
      </section>
      <section aria-label="Version history">
        <h2>Version history</h2>
        {versions.length === 0 ? <p>No published versions yet.</p> : (
          <ul>{versions.map((item) => <li key={item.version}>Version {item.version} <button disabled={!canEdit} onClick={() => restore(item.version)} type="button">Restore version {item.version}</button></li>)}</ul>
        )}
        {restoreMessage ? <p>{restoreMessage}</p> : null}
      </section>
    </section>
  );
}
