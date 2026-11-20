"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/studio/form-field";

import type { AgentTemplateDto } from "./types";

type CreateResult = { state: "created"; agentId: string } | { state: "error"; message: string };

export function AgentCreationWizard({
  templates,
  agentCount,
  maxAgents,
  canEdit,
  createAction,
}: {
  templates: AgentTemplateDto[];
  agentCount: number;
  maxAgents: number;
  canEdit: boolean;
  createAction(input: { mode: "template" | "custom"; templateId?: string; name: string }): Promise<CreateResult>;
}) {
  const [mode, setMode] = useState<"template" | "custom">(templates.length > 0 ? "template" : "custom");
  const [templateId, setTemplateId] = useState(templates[0]?.template_id ?? "");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"idle" | "creating" | "created" | "error">("idle");
  const [createdId, setCreatedId] = useState("");
  const [message, setMessage] = useState("");
  const atLimit = agentCount >= maxAgents;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEdit || atLimit || !name.trim()) return;
    setStatus("creating");
    setMessage("");
    const result = await createAction({ mode, templateId: mode === "template" ? templateId : undefined, name: name.trim() });
    if (result.state === "created") {
      setCreatedId(result.agentId);
      setStatus("created");
    } else {
      setMessage(result.message);
      setStatus("error");
    }
  }

  return (
    <form className="guided-form" onSubmit={submit}>
      {!canEdit ? <div className="inline-notice inline-notice--info"><strong>You have view-only access.</strong> <span>Workspace editors can create agents.</span></div> : null}
      {atLimit ? <div className="inline-notice inline-notice--warning">Your workspace has reached its {maxAgents}-agent limit.</div> : null}
      <section className="form-panel">
        <div className="panel-heading">
          <p className="screen-eyebrow">Starting point</p>
          <h2>Choose how to begin</h2>
          <p>Templates provide editable defaults. Starting from scratch uses Wavia&apos;s safe base configuration.</p>
        </div>
        <fieldset className="choice-grid" disabled={!canEdit || atLimit}>
          <legend className="sr-only">Choose a starting point</legend>
          {templates.map((template) => (
            <label className="choice-card" key={template.template_id}>
              <input aria-label={template.name} checked={mode === "template" && templateId === template.template_id} name="startingPoint" onChange={() => { setMode("template"); setTemplateId(template.template_id); }} type="radio" />
              <span className="choice-card__copy">
                <strong>{template.name}</strong>
                <span>{template.description}</span>
                <small>{template.languages.join(", ").toUpperCase()}</small>
              </span>
            </label>
          ))}
          <label className="choice-card">
            <input aria-label="Start from scratch" checked={mode === "custom"} name="startingPoint" onChange={() => setMode("custom")} type="radio" />
            <span className="choice-card__copy">
              <strong>Start from scratch</strong>
              <span>Begin with the default safe configuration and set each detail yourself.</span>
            </span>
          </label>
        </fieldset>
      </section>
      <section className="form-panel">
        <div className="panel-heading">
          <p className="screen-eyebrow">Identity</p>
          <h2>{mode === "custom" ? "Custom setup" : "Name this agent"}</h2>
          <p>Use a clear internal name. You can change its customer-facing greeting later.</p>
        </div>
        <FormField hint="Visible to members of this workspace." label="Agent name" name="agent-name-create">
          <input disabled={!canEdit || atLimit} value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
      </section>
      <div className="guided-form__actions">
        <div aria-live="polite" className="guided-form__status" role={status === "error" ? "alert" : status === "creating" ? "status" : undefined}>
          {status === "creating" ? "Creating agent…" : status === "error" ? message : null}
        </div>
        <button className="button button--primary" disabled={!canEdit || atLimit || !name.trim() || status === "creating"} type="submit">
          {status === "creating" ? "Creating…" : "Create agent"}
        </button>
      </div>
      {status === "created" ? (
        <div className="creation-success" role="status">
          <div><strong>Agent created</strong><span>Your draft is ready for configuration.</span></div>
          <Link className="button button--primary" href={`/agents/${createdId}/build`}>Continue building</Link>
        </div>
      ) : null}
    </form>
  );
}
