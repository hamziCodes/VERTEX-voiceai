"use client";

import { useState, type FormEvent } from "react";

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

function fileError(file: File, entitlementBytes: number): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const policy = FORMAT_LIMITS[extension];
  if (!policy) return "Choose a PDF, DOCX, TXT, Markdown, CSV, or XLSX file.";
  const limit = Math.min(policy.bytes, entitlementBytes);
  if (file.size > limit) return `${policy.label} files must be ${Math.floor(limit / 1024 / 1024)} MB or smaller.`;
  if (file.size === 0) return "Choose a file that is not empty.";
  return null;
}

function sourceLabel(status: KnowledgeSourceDto["status"]): string {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Failed";
  if (status === "queued") return "Queued";
  if (status === "deleting") return "Deleting";
  return "Processing";
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

  async function remove(source: KnowledgeSourceDto) {
    if (!base || !canEdit) return;
    const result = await actions.deleteSource(base.knowledge_base_id, source.source_id);
    if (result.state === "deleted") setSources((current) => current.filter((item) => item.source_id !== source.source_id));
    else setError(result.message);
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

  if (!base) {
    return (
      <section>
        {!canEdit ? <p>You have view-only access.</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        <p>No knowledge base is selected. Create one to begin adding trusted information.</p>
        <form onSubmit={createBase}>
          <label>Knowledge base name<input disabled={!canEdit || busy} value={baseName} onChange={(event) => setBaseName(event.target.value)} /></label>
          <button disabled={!canEdit || busy || !baseName.trim()} type="submit">Create knowledge base</button>
        </form>
      </section>
    );
  }

  const activationBlocked = !canEdit || sources.length === 0 || sources.some((source) => source.status !== "ready");
  const readySourceCount = sources.filter((source) => source.status === "ready").length;
  const totalChunks = sources.reduce((total, source) => total + source.chunk_count, 0);

  return (
    <section>
      {!canEdit ? <p>You have view-only access.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p aria-live="polite">{message}</p> : null}
      <h2>{base.name}</h2>
      <p>{readySourceCount} of {sources.length} sources ready · {totalChunks} searchable sections</p>

      <section aria-label="Documents">
        <h3>Add documents</h3>
        <p>Supported: PDF, DOCX, TXT, Markdown, CSV, and XLSX.</p>
        <form onSubmit={upload}>
          <label>Choose document<input accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx" disabled={!canEdit || busy} onChange={(event) => chooseFile(event.target.files?.[0])} type="file" /></label>
          <button disabled={!canEdit || !file || busy} type="submit">Upload document</button>
        </form>
        {sources.length === 0 ? <p>No sources added yet.</p> : (
          <ul>{sources.map((source) => (
            <li key={source.source_id}>
              <span>{source.display_name}</span> <strong>{sourceLabel(source.status)}</strong>
              {source.error_message ? <p>{source.error_message}</p> : null}
              {source.status === "failed" ? <button disabled={!canEdit} onClick={() => retry(source)} type="button">Retry source</button> : null}
              <button disabled={!canEdit} onClick={() => remove(source)} type="button">Delete {source.display_name}</button>
            </li>
          ))}</ul>
        )}
      </section>

      <section aria-label="Frequently asked questions">
        <h3>Add an FAQ</h3>
        <form onSubmit={addFaq}>
          <label>FAQ name<input disabled={!canEdit || busy} value={faqName} onChange={(event) => setFaqName(event.target.value)} /></label>
          <label>Question<input disabled={!canEdit || busy} value={faqQuestion} onChange={(event) => setFaqQuestion(event.target.value)} /></label>
          <label>Answer<textarea disabled={!canEdit || busy} value={faqAnswer} onChange={(event) => setFaqAnswer(event.target.value)} /></label>
          <button disabled={!canEdit || busy || !faqName.trim() || !faqQuestion.trim() || !faqAnswer.trim()} type="submit">Add FAQ</button>
        </form>
      </section>

      <section aria-label="Preview knowledge">
        <h3>Preview knowledge</h3>
        <form onSubmit={preview}>
          <label>Ask your knowledge<input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <button disabled={!query.trim()} type="submit">Preview answer</button>
        </form>
        {results?.length === 0 ? <p>No matching information was found.</p> : null}
        {results && results.length > 0 ? <ol>{results.map((result) => <li key={`${result.source_id}:${result.text}`}><p>{result.text}</p><cite>{citationLabel(result.citation)}</cite></li>)}</ol> : null}
      </section>

      <section aria-label="Publish knowledge">
        <h3>Activate and connect</h3>
        {activationBlocked && canEdit ? <p>All sources must finish successfully before activation.</p> : null}
        <button disabled={activationBlocked} onClick={activate} type="button">Activate knowledge</button>
        <label>Agent<select disabled={!canEdit || base.status !== "active" || agents.length === 0} value={selectedAgent} onChange={(event) => setSelectedAgent(event.target.value)}>{agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}</select></label>
        <button disabled={!canEdit || base.status !== "active" || !selectedAgent} onClick={bind} type="button">Connect to agent</button>
      </section>
    </section>
  );
}
