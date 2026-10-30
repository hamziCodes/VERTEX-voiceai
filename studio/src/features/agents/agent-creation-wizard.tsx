"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

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
  const [mode, setMode] = useState<"template" | "custom">("template");
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
    <form onSubmit={submit}>
      {atLimit ? <p>Your workspace has reached its {maxAgents}-agent limit.</p> : null}
      <fieldset disabled={!canEdit || atLimit}>
        <legend>Choose a starting point</legend>
        {templates.map((template) => (
          <label key={template.template_id}>
            <input checked={mode === "template" && templateId === template.template_id} name="startingPoint" onChange={() => { setMode("template"); setTemplateId(template.template_id); }} type="radio" />
            {template.name}
            <span>{template.description}</span>
          </label>
        ))}
        <label><input checked={mode === "custom"} name="startingPoint" onChange={() => setMode("custom")} type="radio" />Start from scratch</label>
      </fieldset>
      {mode === "custom" ? <h2>Custom setup</h2> : null}
      <label>Agent name<input disabled={!canEdit || atLimit} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <button disabled={!canEdit || atLimit || !name.trim() || status === "creating"} type="submit">Create agent</button>
      <p aria-live="polite">{status === "creating" ? "Creating agent…" : status === "error" ? message : null}</p>
      {status === "created" ? <Link href={`/agents/${createdId}/build`}>Continue building</Link> : null}
    </form>
  );
}
