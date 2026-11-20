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
    setValidation(await actions.validateDraft(initialAgent.agent_id));
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
  const issuesFor = (...fields: string[]) => validation.errors.filter((issue) => issue.field !== null && fields.includes(issue.field));
  const nameIssues = issuesFor("name");
  const descriptionIssues = issuesFor("description");
  const languageIssues = issuesFor("languages");
  const greetingIssues = issuesFor("greeting", "persona.greeting");
  const voiceIssues = issuesFor("voice_id", "persona.voice_id");
  const promptIssues = issuesFor("system_prompt", "persona.system_prompt");
  const showStickySave = dirty && saveStatus !== "conflict" && saveStatus !== "error";

  return (
    <section className="persona-editor">
      {!canEdit ? <p className="inline-notice inline-notice--info">You have view-only access.</p> : null}
      <p aria-live="polite" className="sr-only">
        {saveStatus === "saving" ? "Saving…" : null}
        {saveStatus === "saved" ? `Saved at revision ${revision}.` : null}
      </p>
      {saveStatus === "conflict" || saveStatus === "error" ? (
        <div className="inline-notice inline-notice--danger" role="alert">
          <p>{message}</p>
          {saveStatus === "conflict" ? <button className="button button--secondary" onClick={() => window.location.reload()} type="button">Reload latest draft</button> : null}
        </div>
      ) : null}

      <div className="persona-layout">
        <div className="persona-form-column">
          <section aria-labelledby="identity-heading" className="form-panel">
            <div className="panel-heading"><p className="screen-eyebrow">Identity</p><h2 id="identity-heading">Agent details</h2><p>Set the name and internal description operators see in Studio.</p></div>
            <div className="field-stack">
              <label htmlFor="agent-name">Agent name</label>
              <input aria-describedby={nameIssues.length > 0 ? "agent-name-error" : undefined} aria-invalid={nameIssues.length > 0} disabled={!canEdit} id="agent-name" value={draft.name} onChange={(event) => update({ name: event.target.value })} />
              {nameIssues.length > 0 ? <p className="field-error" id="agent-name-error">{nameIssues[0]?.message}</p> : null}
            </div>
            <div className="field-stack">
              <label htmlFor="agent-description">Description</label>
              <textarea aria-describedby={descriptionIssues.length > 0 ? "agent-description-error" : undefined} aria-invalid={descriptionIssues.length > 0} disabled={!canEdit} id="agent-description" value={draft.description} onChange={(event) => update({ description: event.target.value })} />
              {descriptionIssues.length > 0 ? <p className="field-error" id="agent-description-error">{descriptionIssues[0]?.message}</p> : null}
            </div>
          </section>

          <section aria-labelledby="conversation-heading" className="form-panel">
            <div className="panel-heading"><p className="screen-eyebrow">Conversation</p><h2 id="conversation-heading">Opening and voice</h2><p>Control the first words callers hear and the voice configuration used by this draft.</p></div>
            <div className="field-grid">
              <div className="field-stack">
                <label htmlFor="agent-languages">Languages</label>
                <input aria-describedby={languageIssues.length > 0 ? "agent-languages-error" : "agent-languages-help"} aria-invalid={languageIssues.length > 0} disabled={!canEdit} id="agent-languages" value={draft.languages.join(", ")} onChange={(event) => update({ languages: event.target.value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean) })} />
                <p className="field-help" id="agent-languages-help">Comma-separated language codes.</p>
                {languageIssues.length > 0 ? <p className="field-error" id="agent-languages-error">{languageIssues[0]?.message}</p> : null}
              </div>
              <div className="field-stack">
                <label htmlFor="agent-voice">Voice</label>
                <input aria-describedby={voiceIssues.length > 0 ? "agent-voice-error" : undefined} aria-invalid={voiceIssues.length > 0} disabled={!canEdit} id="agent-voice" value={draft.persona.voice_id} onChange={(event) => update({ persona: { ...draft.persona, voice_id: event.target.value } })} />
                {voiceIssues.length > 0 ? <p className="field-error" id="agent-voice-error">{voiceIssues[0]?.message}</p> : null}
              </div>
            </div>
            <div className="field-stack">
              <label htmlFor="agent-greeting">Greeting</label>
              <input aria-describedby={greetingIssues.length > 0 ? "agent-greeting-error" : undefined} aria-invalid={greetingIssues.length > 0} disabled={!canEdit} id="agent-greeting" value={draft.persona.greeting ?? ""} onChange={(event) => update({ persona: { ...draft.persona, greeting: event.target.value || null } })} />
              {greetingIssues.length > 0 ? <p className="field-error" id="agent-greeting-error">{greetingIssues[0]?.message}</p> : null}
            </div>
          </section>

          <section aria-label="Advanced settings" className="form-panel form-panel--disclosure">
            <button aria-expanded={advancedOpen} className="disclosure-button" onClick={() => setAdvancedOpen((open) => !open)} type="button"><span>Advanced</span><span aria-hidden="true">{advancedOpen ? "−" : "+"}</span></button>
            {advancedOpen ? (
              <div className="disclosure-content">
                <div className="inline-notice inline-notice--warning" role="note"><strong>Tenant data boundary</strong><p>Tenant data stays isolated from Wavia&apos;s core prompts and is used only for this agent&apos;s configured behavior.</p></div>
                <div className="field-stack">
                  <label htmlFor="agent-system-prompt">System prompt</label>
                  <textarea aria-describedby={promptIssues.length > 0 ? "agent-system-prompt-error" : "agent-system-prompt-help"} aria-invalid={promptIssues.length > 0} disabled={!canEdit} id="agent-system-prompt" value={draft.persona.system_prompt} onChange={(event) => update({ persona: { ...draft.persona, system_prompt: event.target.value } })} />
                  <p className="field-help" id="agent-system-prompt-help">Provider routing is preserved from the selected template.</p>
                  {promptIssues.length > 0 ? <p className="field-error" id="agent-system-prompt-error">{promptIssues[0]?.message}</p> : null}
                </div>
              </div>
            ) : null}
          </section>
        </div>

        <aside className="persona-side-column">
          <section aria-label="Readiness" className="side-panel">
            <p className="screen-eyebrow">Release</p>
            <h2>Publish readiness</h2>
            {validation.is_valid ? <p className="readiness-state readiness-state--ready">Ready to publish.</p> : validation.errors.length > 0 ? <ul className="validation-list">{validation.errors.map((issue) => <li key={`${issue.code}:${issue.field ?? "root"}`}>{issue.message}</li>)}</ul> : <p className="readiness-state">Run the check after your latest changes.</p>}
            <div className="panel-actions">
              <button className="button button--secondary" disabled={!canEdit || dirty || saveStatus === "saving" || saveStatus === "conflict"} onClick={validate} type="button">Check readiness</button>
              <button className="button button--primary" disabled={publishBlocked} onClick={publish} type="button">Publish agent</button>
            </div>
            {publishedVersion ? <p className="inline-success">Published version {publishedVersion}.</p> : null}
          </section>

          <section aria-label="Version history" className="side-panel">
            <h2>Version history</h2>
            {versions.length === 0 ? <p className="muted-copy">No published versions yet.</p> : (
              <ul className="version-list">{versions.map((item) => <li key={item.version}><span>Version {item.version}</span><button className="text-action" disabled={!canEdit} onClick={() => restore(item.version)} type="button">Restore version {item.version}</button></li>)}</ul>
            )}
            {restoreMessage ? <p className="inline-success">{restoreMessage}</p> : null}
          </section>
        </aside>
      </div>

      {showStickySave ? (
        <div aria-label="Draft save status" className="sticky-save-bar" role="status">
          <span aria-hidden="true" className="save-indicator" />
          <strong>Saving changes</strong>
          <span>Autosave is on</span>
        </div>
      ) : null}
    </section>
  );
}
