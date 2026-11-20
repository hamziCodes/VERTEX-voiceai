"use client";

import { useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/studio/confirm-dialog";
import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";
import { formatNumber } from "@/lib/format";

import type { KnowledgeActions, KnowledgeAgentOption, KnowledgeBaseDto, KnowledgePreviewResultDto, KnowledgeSourceDto } from "./types";

const FORMAT_LIMITS: Readonly<Record<string, { label: string; bytes: number }>> = {
  pdf: { label: "PDF", bytes: 20 * 1024 * 1024 },
  docx: { label: "DOCX", bytes: 10 * 1024 * 1024 },
  txt: { label: "TXT", bytes: 5 * 1024 * 1024 },
  md: { label: "Markdown", bytes: 5 * 1024 * 1024 },
  markdown: { label: "Markdown", bytes: 5 * 1024 * 1024 },
  csv: { label: "CSV", bytes: 10 * 1024 * 1024 },
  xlsx: { label: "XLSX", bytes: 10 * 1024 * 1024 },
};

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

function fileError(file: File, entitlementBytes: number): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const policy = FORMAT_LIMITS[extension];
  if (!policy) return "Choose a PDF, DOCX, TXT, Markdown, CSV, or XLSX file.";
  const limit = Math.min(policy.bytes, entitlementBytes);
  if (file.size > limit) return `${policy.label} files must be ${Math.floor(limit / 1024 / 1024)} MB or smaller.`;
  if (file.size === 0) return "Choose a file that is not empty.";
  return null;
}

function sourceStatus(status: KnowledgeSourceDto["status"]): { label: string; tone: BadgeTone } {
  if (status === "ready") return { label: "Ready", tone: "success" };
  if (status === "failed") return { label: "Failed", tone: "danger" };
  if (status === "queued") return { label: "Queued", tone: "info" };
  if (status === "deleting") return { label: "Deleting", tone: "neutral" };
  return { label: "Processing", tone: "warning" };
}

function baseStatus(base: KnowledgeBaseDto): { label: string; tone: BadgeTone } {
  if (base.status === "active") return { label: `Active · revision ${base.active_revision}`, tone: "success" };
  if (base.status === "ready") return { label: "Ready to activate", tone: "info" };
  if (base.status === "failed") return { label: "Needs attention", tone: "danger" };
  if (base.status === "processing") return { label: "Processing", tone: "warning" };
  if (base.status === "deleting") return { label: "Deleting", tone: "neutral" };
  return { label: "Draft", tone: "neutral" };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${formatNumber(bytes / 1024)} KB`;
  return `${formatNumber(bytes / 1024 / 1024)} MB`;
}

function citationLabel(citation: Record<string, unknown>): string {
  const heading = typeof citation.heading === "string" ? citation.heading : "Source";
  const line = typeof citation.line_start === "number" ? ` · line ${citation.line_start}` : "";
  return `${heading}${line}`;
}

export function KnowledgeManager({
  base: initialBase,
  sources: initialSources,
  agents,
  maxUploadBytes,
  canEdit,
  actions,
}: {
  base: KnowledgeBaseDto | null;
  sources: KnowledgeSourceDto[];
  agents: KnowledgeAgentOption[];
  maxUploadBytes: number;
  canEdit: boolean;
  actions: KnowledgeActions;
}) {
  const [base, setBase] = useState(initialBase);
  const [sources, setSources] = useState(initialSources);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgePreviewResultDto[] | null>(null);
  const [selectedAgent, setSelectedAgent] = useState(agents[0]?.agent_id ?? "");
  const [busy, setBusy] = useState(false);
  const [baseName, setBaseName] = useState("");
  const [faqName, setFaqName] = useState("FAQ");
  const [faqQuestion, setFaqQuestion] = useState("");
  const [faqAnswer, setFaqAnswer] = useState("");
  const [deleting, setDeleting] = useState<KnowledgeSourceDto | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function createBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!baseName.trim() || !canEdit) return;
    setBusy(true);
    setError("");
    const result = await actions.createBase(baseName.trim());
    setBusy(false);
    if (result.state === "created") {
      setBase(result.knowledgeBase);
      setSources([]);
      setMessage(`${result.knowledgeBase.name} was created.`);
    } else setError(result.message);
  }

  function chooseFile(next: File | undefined) {
    setMessage("");
    if (!next) {
      setFile(null);
      setError("");
      return;
    }
    const issue = fileError(next, maxUploadBytes);
    setFile(issue ? null : next);
    setError(issue ?? "");
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!base || !file || !canEdit) return;
    setBusy(true);
    setError("");
    const result = await actions.uploadSource(base.knowledge_base_id, file);
    setBusy(false);
    if (result.state === "uploaded") {
      setSources((current) => [...current, result.source]);
      setFile(null);
      setMessage(`${result.source.display_name} was queued for processing.`);
    } else {
      setError(result.message);
    }
  }

  async function confirmDelete() {
    if (!base || !deleting || !canEdit) return;
    setDeleteBusy(true);
    setDeleteError(null);
    const target = deleting;
    const result = await actions.deleteSource(base.knowledge_base_id, target.source_id);
    setDeleteBusy(false);
    if (result.state === "deleted") {
      setSources((current) => current.filter((item) => item.source_id !== target.source_id));
      setDeleting(null);
      setMessage(`${target.display_name} was deleted.`);
    } else setDeleteError(result.message);
  }

  async function addFaq(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!base || !canEdit || !faqName.trim() || !faqQuestion.trim() || !faqAnswer.trim()) return;
    setBusy(true);
    setError("");
    const result = await actions.addFaq(base.knowledge_base_id, { name: faqName.trim(), question: faqQuestion.trim(), answer: faqAnswer.trim() });
    setBusy(false);
    if (result.state === "uploaded") {
      setSources((current) => [...current, result.source]);
      setFaqQuestion("");
      setFaqAnswer("");
      setMessage(`${result.source.display_name} was queued for processing.`);
    } else setError(result.message);
  }

  async function retry(source: KnowledgeSourceDto) {
    if (!base || !canEdit) return;
    const result = await actions.retrySource(base.knowledge_base_id, source.source_id);
    if (result.state === "queued") setSources((current) => current.map((item) => item.source_id === source.source_id ? { ...item, status: "queued", error_code: null, error_message: null } : item));
    else setError(result.message);
  }

  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!base || !query.trim()) return;
    const result = await actions.preview(base.knowledge_base_id, query.trim());
    if (result.state === "complete") setResults(result.results);
    else setError(result.message);
  }

  async function activate() {
    if (!base || !canEdit) return;
    const result = await actions.activate(base.knowledge_base_id);
    if (result.state === "active") {
      setBase(result.knowledgeBase);
      setMessage(`Knowledge revision ${result.knowledgeBase.active_revision} is active.`);
    } else setError(result.message);
  }

  async function bind() {
    if (!base || !selectedAgent || !canEdit) return;
    const result = await actions.bindAgent(base.knowledge_base_id, selectedAgent);
    if (result.state === "bound") {
      const agentName = agents.find((agent) => agent.agent_id === selectedAgent)?.name ?? "agent";
      setMessage(`Connected to ${agentName} as published agent version ${result.agentVersion}.`);
    } else setError(result.message);
  }

  const notices = (
    <>
      {!canEdit ? <p className="inline-notice inline-notice--info">You have view-only access.</p> : null}
      {error ? <p className="inline-notice inline-notice--danger" role="alert">{error}</p> : null}
      {message ? <p className="inline-notice inline-notice--success" role="status">{message}</p> : null}
    </>
  );

  if (!base) {
    return (
      <div className="knowledge-workspace">
        {notices}
        <form aria-labelledby="knowledge-create-heading" className="form-panel knowledge-create" onSubmit={createBase}>
          <div className="panel-heading">
            <p className="screen-eyebrow">Start here</p>
            <h2 id="knowledge-create-heading">Create a knowledge base</h2>
            <p>No knowledge base is selected. Create one to begin adding trusted information.</p>
          </div>
          <FormField hint="Visible to members of this workspace, for example Store policies." label="Knowledge base name" name="knowledge-base-name">
            <input disabled={!canEdit || busy} maxLength={255} onChange={(event) => setBaseName(event.target.value)} value={baseName} />
          </FormField>
          <div className="panel-actions panel-actions--inline">
            <button className="button button--primary" disabled={!canEdit || busy || !baseName.trim()} type="submit">Create knowledge base</button>
          </div>
        </form>
      </div>
    );
  }

  const activationBlocked = !canEdit || sources.length === 0 || sources.some((source) => source.status !== "ready");
  const readySourceCount = sources.filter((source) => source.status === "ready").length;
  const totalChunks = sources.reduce((total, source) => total + source.chunk_count, 0);
  const status = baseStatus(base);

  return (
    <div className="knowledge-workspace">
      {notices}
      <section aria-labelledby="knowledge-base-heading" className="knowledge-summary">
        <div>
          <div className="knowledge-summary__title">
            <h2 id="knowledge-base-heading">{base.name}</h2>
            <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
          </div>
          <p>{readySourceCount} of {sources.length} sources ready · {totalChunks} searchable sections</p>
        </div>
      </section>

      <div className="knowledge-layout">
        <div className="knowledge-column">
          <section aria-label="Documents" className="form-panel">
            <div className="panel-heading">
              <p className="screen-eyebrow">Sources</p>
              <h3>Add documents</h3>
              <p>Supported: PDF, DOCX, TXT, Markdown, CSV, and XLSX.</p>
            </div>
            <form className="knowledge-upload" onSubmit={upload}>
              <FormField label="Choose document" name="knowledge-document">
                <input accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx" disabled={!canEdit || busy} onChange={(event) => chooseFile(event.target.files?.[0])} type="file" />
              </FormField>
              <button className="button button--primary" disabled={!canEdit || !file || busy} type="submit">Upload document</button>
            </form>
            {sources.length === 0 ? (
              <p className="knowledge-empty">No sources added yet.</p>
            ) : (
              <ul aria-label="Knowledge sources" className="knowledge-source-list">
                {sources.map((source) => {
                  const state = sourceStatus(source.status);
                  return (
                    <li aria-label={source.display_name} className="knowledge-source" key={source.source_id}>
                      <div className="knowledge-source__copy">
                        <div className="knowledge-source__title">
                          <strong>{source.display_name}</strong>
                          <StatusBadge tone={state.tone}>{state.label}</StatusBadge>
                        </div>
                        <span className="knowledge-source__meta">{source.source_type.toUpperCase()} · {formatBytes(source.byte_count)} · {source.chunk_count} sections</span>
                        {source.error_message ? <p className="knowledge-source__error">{source.error_message}</p> : null}
                      </div>
                      <div className="knowledge-source__actions">
                        {source.status === "failed" ? <button className="button button--secondary" disabled={!canEdit} onClick={() => retry(source)} type="button">Retry source</button> : null}
                        <button
                          aria-label={`Delete ${source.display_name}`}
                          className="button button--quiet-danger"
                          disabled={!canEdit}
                          onClick={() => { setDeleteError(null); setDeleting(source); }}
                          type="button"
                        >
                          Delete
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section aria-label="Frequently asked questions" className="form-panel">
            <div className="panel-heading">
              <p className="screen-eyebrow">Sources</p>
              <h3>Add an FAQ</h3>
              <p>Write one question and its approved answer.</p>
            </div>
            <form className="knowledge-form" onSubmit={addFaq}>
              <FormField label="FAQ name" name="faq-name">
                <input disabled={!canEdit || busy} onChange={(event) => setFaqName(event.target.value)} value={faqName} />
              </FormField>
              <FormField label="Question" name="faq-question">
                <input disabled={!canEdit || busy} onChange={(event) => setFaqQuestion(event.target.value)} value={faqQuestion} />
              </FormField>
              <FormField label="Answer" name="faq-answer">
                <textarea disabled={!canEdit || busy} onChange={(event) => setFaqAnswer(event.target.value)} rows={4} value={faqAnswer} />
              </FormField>
              <div className="panel-actions panel-actions--inline">
                <button className="button button--secondary" disabled={!canEdit || busy || !faqName.trim() || !faqQuestion.trim() || !faqAnswer.trim()} type="submit">Add FAQ</button>
              </div>
            </form>
          </section>
        </div>

        <div className="knowledge-column">
          <section aria-label="Preview knowledge" className="form-panel">
            <div className="panel-heading">
              <p className="screen-eyebrow">Verify</p>
              <h3>Preview knowledge</h3>
              <p>See which passages an agent would retrieve, with their citations.</p>
            </div>
            <form className="knowledge-form" onSubmit={preview}>
              <FormField label="Ask your knowledge" name="knowledge-query">
                <input onChange={(event) => setQuery(event.target.value)} value={query} />
              </FormField>
              <div className="panel-actions panel-actions--inline">
                <button className="button button--secondary" disabled={!query.trim()} type="submit">Preview answer</button>
              </div>
            </form>
            {results?.length === 0 ? <p className="knowledge-empty">No matching information was found.</p> : null}
            {results && results.length > 0 ? (
              <ol className="knowledge-results">
                {results.map((result) => (
                  <li key={`${result.source_id}:${result.text}`}>
                    <p>{result.text}</p>
                    <cite className="technical-value">{citationLabel(result.citation)}</cite>
                  </li>
                ))}
              </ol>
            ) : null}
          </section>

          <section aria-label="Publish knowledge" className="form-panel">
            <div className="panel-heading">
              <p className="screen-eyebrow">Publish</p>
              <h3>Activate and connect</h3>
              <p>Activation freezes the ready sources as a revision. Connecting publishes a new agent version that uses it.</p>
            </div>
            {activationBlocked && canEdit ? <p className="field-help">All sources must finish successfully before activation.</p> : null}
            <div className="panel-actions panel-actions--inline">
              <button className="button button--primary" disabled={activationBlocked} onClick={activate} type="button">Activate knowledge</button>
            </div>
            {agents.length === 0 ? (
              <p className="field-help">No agent is available to connect yet.</p>
            ) : (
              <div className="knowledge-connect">
                <FormField label="Agent" name="knowledge-agent">
                  <select disabled={!canEdit || base.status !== "active"} onChange={(event) => setSelectedAgent(event.target.value)} value={selectedAgent}>
                    {agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}
                  </select>
                </FormField>
                <button className="button button--secondary" disabled={!canEdit || base.status !== "active" || !selectedAgent} onClick={bind} type="button">Connect to agent</button>
              </div>
            )}
          </section>
        </div>
      </div>

      {deleting ? (
        <ConfirmDialog
          busy={deleteBusy}
          confirmLabel="Delete source"
          error={deleteError}
          onCancel={() => { setDeleting(null); setDeleteError(null); }}
          onConfirm={() => void confirmDelete()}
          title="Delete source"
        >
          <p>
            Delete “{deleting.display_name}” from {base.name}? Its searchable sections are removed from this knowledge base. To use it again, upload it again.
          </p>
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
