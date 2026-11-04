"use client";

import { useState } from "react";
import type { AgentSummary } from "./types";

export interface WebChannelViewProps {
  agents: AgentSummary[];
  defaultAgentId?: string;
}

export function WebChannelView({ agents, defaultAgentId }: WebChannelViewProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    defaultAgentId ?? agents[0]?.agent_id ?? "YOUR_AGENT_ID"
  );
  const [copiedScript, setCopiedScript] = useState(false);
  const [copiedNpm, setCopiedNpm] = useState(false);

  const selectedAgent = agents.find((a) => a.agent_id === selectedAgentId);

  const npmSnippet = "npm install @ucve/voice-sdk";

  const scriptSnippet = `// 1. Request an ephemeral session token from your backend server
// Your backend mints this token using your secret API key (never expose keys in frontend code).
const response = await fetch("https://YOUR_SERVER_MINT_ENDPOINT/api/voice/session", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ agent_id: "${selectedAgentId}" })
});
const { ws_url, token } = await response.json();

// 2. Connect with the public @ucve/voice-sdk API
import { UCVEVoiceClient } from "@ucve/voice-sdk";

const client = new UCVEVoiceClient(token, {
  wsUrl: ws_url,
  onTranscript: (speaker, text) => {
    console.log(\`[\${speaker}]: \${text}\`);
  }
});

await client.connect();`;

  async function handleCopy(text: string, setCopied: (v: boolean) => void) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <header>
        <h2>Web Voice Integration</h2>
        <p>
          Integrate real-time AI voice agents directly into your web applications using the official{" "}
          <code>@ucve/voice-sdk</code> package.
        </p>
      </header>

      <section style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <label htmlFor="agent-selector" style={{ fontWeight: 600 }}>
          Select Agent
        </label>
        <select
          id="agent-selector"
          aria-label="Select Agent"
          value={selectedAgentId}
          onChange={(e) => setSelectedAgentId(e.target.value)}
          style={{ maxWidth: "400px", padding: "0.5rem" }}
        >
          {agents.map((agent) => (
            <option key={agent.agent_id} value={agent.agent_id}>
              {agent.name} {agent.is_published ? "(Published)" : "(Draft)"} - {agent.agent_id}
            </option>
          ))}
          {agents.length === 0 && (
            <option value="YOUR_AGENT_ID">No agents created yet</option>
          )}
        </select>
        {selectedAgent && (
          <small style={{ color: "#666" }}>
            Target Agent: <code>{selectedAgent.agent_id}</code>
          </small>
        )}
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <h3>Step 1: Install SDK</h3>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <pre
            style={{
              background: "#f4f4f5",
              padding: "0.75rem",
              borderRadius: "4px",
              fontFamily: "monospace",
              margin: 0,
            }}
          >
            {npmSnippet}
          </pre>
          <button
            type="button"
            onClick={() => handleCopy(npmSnippet, setCopiedNpm)}
          >
            {copiedNpm ? "Copied!" : "Copy Command"}
          </button>
        </div>
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <h3>Step 2: Connect via Client SDK</h3>
        <p style={{ fontSize: "0.9rem", color: "#555" }}>
          For security, frontend clients never use raw API keys. Your server mints a single-use token
          with <code>/v1/session/mint</code>, which the browser passes to <code>UCVEVoiceClient</code>.
        </p>
        <div style={{ position: "relative" }}>
          <pre
            data-testid="embed-code-snippet"
            style={{
              background: "#18181b",
              color: "#fafafa",
              padding: "1rem",
              borderRadius: "6px",
              overflowX: "auto",
              fontFamily: "monospace",
              fontSize: "0.85rem",
            }}
          >
            {scriptSnippet}
          </pre>
          <button
            type="button"
            onClick={() => handleCopy(scriptSnippet, setCopiedScript)}
            style={{ marginTop: "0.5rem" }}
          >
            {copiedScript ? "Copied!" : "Copy Code"}
          </button>
        </div>
      </section>
    </div>
  );
}
