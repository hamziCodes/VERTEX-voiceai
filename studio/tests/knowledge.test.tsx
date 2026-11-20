// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { loaders, requireWorkspace } = vi.hoisted(() => ({
  loaders: {
    loadKnowledgeAgents: vi.fn(),
    loadKnowledgeBases: vi.fn(),
    loadKnowledgeEntitlements: vi.fn(),
    loadKnowledgeSources: vi.fn(),
  },
  requireWorkspace: vi.fn(),
}));

vi.mock("@/features/knowledge/data", () => loaders);
vi.mock("@/features/knowledge/actions", () => ({
  activateKnowledgeBaseAction: vi.fn(),
  addKnowledgeFaqAction: vi.fn(),
  bindKnowledgeToAgentAction: vi.fn(),
  createKnowledgeBaseAction: vi.fn(),
  deleteKnowledgeSourceAction: vi.fn(),
  previewKnowledgeAction: vi.fn(),
  retryKnowledgeSourceAction: vi.fn(),
  uploadKnowledgeSourceAction: vi.fn(),
}));
vi.mock("@/auth/workspace", async () => {
  const permissions = await import("@/auth/workspace-permissions");
  return { hasWorkspaceCapability: permissions.hasWorkspaceCapability, requireWorkspace };
});

import KnowledgePage from "@/app/(studio)/knowledge/page";
import { KnowledgeManager } from "@/features/knowledge/knowledge-manager";
import type { KnowledgeBaseDto, KnowledgeSourceDto } from "@/features/knowledge/types";

const base: KnowledgeBaseDto = {
  knowledge_base_id: "11111111-1111-4111-8111-111111111111",
  name: "Store policies",
  status: "processing",
  active_revision: 0,
  source_count: 4,
  ready_source_count: 1,
  total_chunks: 3,
};

const ready: KnowledgeSourceDto = {
  source_id: "21111111-1111-4111-8111-111111111111",
  knowledge_base_id: base.knowledge_base_id,
  source_type: "txt",
  display_name: "refunds.txt",
  media_type: "text/plain",
  byte_count: 120,
  revision: 1,
  status: "ready",
  chunk_count: 3,
  error_code: null,
  error_message: null,
};

const processing: KnowledgeSourceDto = { ...ready, source_id: "31111111-1111-4111-8111-111111111111", display_name: "catalog.docx", status: "embedding", chunk_count: 0 };
const failed: KnowledgeSourceDto = { ...ready, source_id: "41111111-1111-4111-8111-111111111111", display_name: "hours.csv", status: "failed", chunk_count: 0, error_code: "parser_timeout", error_message: "Processing timed out." };

function actions() {
  return {
    createBase: vi.fn(),
    uploadSource: vi.fn(),
    addFaq: vi.fn(),
    deleteSource: vi.fn(),
    retrySource: vi.fn(),
    preview: vi.fn(),
    activate: vi.fn(),
    bindAgent: vi.fn(),
  };
}

afterEach(cleanup);

describe("knowledge lifecycle", () => {
  it("creates the first knowledge base without asking for an internal ID", async () => {
    const api = actions();
    api.createBase.mockResolvedValue({ state: "created", knowledgeBase: { ...base, source_count: 0, ready_source_count: 0, total_chunks: 0 } });
    const { container } = render(<KnowledgeManager base={null} sources={[]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.change(screen.getByLabelText("Knowledge base name"), { target: { value: "Store policies" } });
    fireEvent.click(screen.getByRole("button", { name: "Create knowledge base" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Store policies" })).toBeVisible());
    expect(container.textContent).not.toContain(base.knowledge_base_id);
  });

  it("adds a question and answer as a queued FAQ source", async () => {
    const api = actions();
    const faqSource = { ...ready, source_id: "61111111-1111-4111-8111-111111111111", display_name: "Returns FAQ.json", source_type: "faq", media_type: "application/json", status: "queued" as const, chunk_count: 0 };
    api.addFaq.mockResolvedValue({ state: "uploaded", source: faqSource });
    render(<KnowledgeManager base={{ ...base, source_count: 0, ready_source_count: 0, total_chunks: 0 }} sources={[]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.change(screen.getByLabelText("FAQ name"), { target: { value: "Returns FAQ" } });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How long do returns take?" } });
    fireEvent.change(screen.getByLabelText("Answer"), { target: { value: "Returns are accepted within 30 days." } });
    fireEvent.click(screen.getByRole("button", { name: "Add FAQ" }));
    await waitFor(() => expect(screen.getByText("Returns FAQ.json")).toBeVisible());
    expect(within(screen.getByRole("listitem", { name: "Returns FAQ.json" })).getByText("Queued")).toBeVisible();
    expect(screen.getByText("0 of 1 sources ready · 0 searchable sections")).toBeVisible();
  });

  it("rejects unsupported and oversized files before upload", () => {
    const api = actions();
    render(<KnowledgeManager base={base} sources={[]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);
    const input = screen.getByLabelText("Choose document") as HTMLInputElement;

    fireEvent.change(input, { target: { files: [new File(["binary"], "malware.exe", { type: "application/octet-stream" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF, DOCX, TXT, Markdown, CSV, or XLSX file.");

    const large = new File(["small fixture"], "large.txt", { type: "text/plain" });
    Object.defineProperty(large, "size", { value: 5 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [large] } });
    expect(screen.getByRole("alert")).toHaveTextContent("TXT files must be 5 MB or smaller.");
    expect(api.uploadSource).not.toHaveBeenCalled();
  });

  it("shows honest mixed states and retries only failed sources", async () => {
    const api = actions();
    api.retrySource.mockResolvedValue({ state: "queued", sourceId: failed.source_id });
    render(<KnowledgeManager base={base} sources={[ready, processing, failed]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    expect(within(screen.getByRole("listitem", { name: "refunds.txt" })).getByText("Ready")).toBeVisible();
    expect(within(screen.getByRole("listitem", { name: "catalog.docx" })).getByText("Processing")).toBeVisible();
    const failedRow = screen.getByRole("listitem", { name: "hours.csv" });
    expect(within(failedRow).getByText("Failed")).toBeVisible();
    expect(within(failedRow).getByText("Processing timed out.")).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Retry source" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry source" }));
    await waitFor(() => expect(within(screen.getByRole("listitem", { name: "hours.csv" })).getByText("Queued")).toBeVisible());
  });

  it("asks for confirmation and removes a source only after the delete action succeeds", async () => {
    const api = actions();
    api.deleteSource.mockResolvedValue({ state: "deleted" });
    render(<KnowledgeManager base={base} sources={[ready]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete refunds.txt" }));
    const dialog = screen.getByRole("dialog", { name: "Delete source" });
    expect(dialog).toHaveTextContent("refunds.txt");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(api.deleteSource).not.toHaveBeenCalled();
    expect(screen.getByText("refunds.txt", { selector: "strong" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Delete refunds.txt" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "Delete source" })).getByRole("button", { name: "Delete source" }));
    await waitFor(() => expect(screen.queryByText("refunds.txt")).not.toBeInTheDocument());
    expect(api.deleteSource).toHaveBeenCalledWith(base.knowledge_base_id, ready.source_id);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the delete confirmation open with the failure when deletion fails", async () => {
    const api = actions();
    api.deleteSource.mockResolvedValue({ state: "error", message: "The source could not be deleted." });
    render(<KnowledgeManager base={base} sources={[ready]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete refunds.txt" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete source" }));
    await waitFor(() => expect(within(screen.getByRole("dialog")).getByRole("alert")).toHaveTextContent("The source could not be deleted."));
    expect(screen.getByText("refunds.txt", { selector: "strong" })).toBeVisible();
  });

  it("renders empty retrieval honestly and then shows source-backed citations", async () => {
    const api = actions();
    api.preview
      .mockResolvedValueOnce({ state: "complete", results: [] })
      .mockResolvedValueOnce({ state: "complete", results: [{ source_id: ready.source_id, text: "Refunds are available within 30 days.", citation: { heading: "Refund policy", line_start: 12 }, score: 0.91 }] });
    render(<KnowledgeManager base={{ ...base, status: "ready" }} sources={[ready]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.change(screen.getByLabelText("Ask your knowledge"), { target: { value: "Do you handle exchanges?" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview answer" }));
    await waitFor(() => expect(screen.getByText("No matching information was found.")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Preview answer" }));
    await waitFor(() => expect(screen.getByText("Refunds are available within 30 days.")).toBeVisible());
    expect(screen.getByText("Refund policy · line 12")).toBeVisible();
  });

  it("blocks activation until every source is ready and reports permanent upload failures", async () => {
    const api = actions();
    api.uploadSource.mockResolvedValue({ state: "error", message: "This document cannot be processed." });
    render(<KnowledgeManager base={base} sources={[ready, processing]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);
    expect(screen.getByRole("button", { name: "Activate knowledge" })).toBeDisabled();

    cleanup();
    render(<KnowledgeManager base={base} sources={[ready]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);
    expect(screen.getByRole("button", { name: "Activate knowledge" })).toBeEnabled();
    const input = screen.getByLabelText("Choose document") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["hello"], "notes.txt", { type: "text/plain" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("This document cannot be processed."));
    expect(screen.queryByRole("button", { name: "Retry upload" })).not.toBeInTheDocument();
  });

  it("activates ready knowledge, binds it to a named agent, and keeps viewers read-only", async () => {
    const api = actions();
    api.activate.mockResolvedValue({ state: "active", knowledgeBase: { ...base, status: "active", active_revision: 1 } });
    api.bindAgent.mockResolvedValue({ state: "bound", agentVersion: 2, knowledgeRevision: 1 });
    const agent = { agent_id: "51111111-1111-4111-8111-111111111111", name: "Store assistant" };
    const { rerender } = render(<KnowledgeManager base={{ ...base, status: "ready" }} sources={[ready]} agents={[agent]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={api} />);

    fireEvent.click(screen.getByRole("button", { name: "Activate knowledge" }));
    await waitFor(() => expect(screen.getByText("Knowledge revision 1 is active.")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Connect to agent" }));
    await waitFor(() => expect(screen.getByText("Connected to Store assistant as published agent version 2.")).toBeVisible());

    rerender(<KnowledgeManager base={{ ...base, status: "active", active_revision: 1 }} sources={[ready]} agents={[agent]} maxUploadBytes={10 * 1024 * 1024} canEdit={false} actions={api} />);
    expect(screen.getByText("You have view-only access.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete refunds.txt" })).toBeDisabled();
  });

  it("renders composed panels without inline styles and explains why activation is blocked", () => {
    const { container } = render(<KnowledgeManager base={base} sources={[ready, processing]} agents={[]} maxUploadBytes={10 * 1024 * 1024} canEdit actions={actions()} />);

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    for (const name of ["Documents", "Frequently asked questions", "Preview knowledge", "Publish knowledge"]) {
      expect(screen.getByRole("region", { name })).toBeVisible();
    }
    expect(screen.getByText("All sources must finish successfully before activation.")).toBeVisible();
    expect(screen.getByText("No agent is available to connect yet.")).toBeVisible();
  });
});

describe("knowledge page", () => {
  const second: KnowledgeBaseDto = { ...base, knowledge_base_id: "71111111-1111-4111-8111-111111111111", name: "Returns" };

  it("uses the shared header and marks the selected knowledge base", async () => {
    requireWorkspace.mockResolvedValue({
      session: { accessToken: "offline" },
      membership: { tenant_id: "11111111-1111-4111-8111-111111111111", capabilities: ["knowledge:read"] },
    });
    loaders.loadKnowledgeBases.mockResolvedValue([base, second]);
    loaders.loadKnowledgeAgents.mockResolvedValue([]);
    loaders.loadKnowledgeEntitlements.mockResolvedValue({ max_knowledge_bytes: 10 * 1024 * 1024 });
    loaders.loadKnowledgeSources.mockResolvedValue([]);

    render(await KnowledgePage({ searchParams: Promise.resolve({ knowledgeBase: second.knowledge_base_id }) }));

    expect(requireWorkspace).toHaveBeenCalledWith("knowledge:read");
    expect(screen.getByRole("heading", { level: 1, name: "Knowledge" })).toBeVisible();
    const switcher = screen.getByRole("navigation", { name: "Knowledge bases" });
    expect(within(switcher).getByRole("link", { name: "Returns" })).toHaveAttribute("aria-current", "page");
    expect(within(switcher).getByRole("link", { name: "Store policies" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("You have view-only access.")).toBeVisible();
  });
});
