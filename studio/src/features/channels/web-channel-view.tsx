"use client";

import { useState } from "react";

import { FormField } from "@/components/studio/form-field";
import { StatusBadge } from "@/components/studio/status-badge";

import type { AgentSummary } from "./types";

export interface WebChannelViewProps {
  agents: AgentSummary[];
  defaultAgentId?: string;
}

export function WebChannelView({ agents, defaultAgentId }: WebChannelViewProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    defaultAgentId ?? agents[0]?.agent_id ?? "YOUR_AGENT_ID"
  );
  const [copied, setCopied] = useState<"npm" | "script" | null>(null);

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

  async function handleCopy(text: string, which: "npm" | "script") {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied((current) => (current === which ? null : current)), 2000);
    }
  }

  return (
    <div className="channel-view">
      <section aria-labelledby="web-channel-heading" className="form-panel">
        <div className="panel-heading">
          <p className="screen-eyebrow">Web</p>
          <h2 id="web-channel-heading">Web voice integration</h2>
          <p>
            Add a real-time voice agent to your web application with the official <code className="technical-value">@ucve/voice-sdk</code> package.
          </p>
        </div>
        {agents.length === 0 ? (
          <p className="inline-notice inline-notice--info">No agents yet. Create and publish an agent, then return here for its integration snippet.</p>
        ) : (
          <div className="channel-agent-picker">
            <FormField label="Select agent" name="agent-selector">
              <select onChange={(e) => setSelectedAgentId(e.target.value)} value={selectedAgentId}>
                {agents.map((agent) => (
                  <option key={agent.agent_id} value={agent.agent_id}>
                    {agent.name} · {agent.is_published ? "Published" : "Draft"}
                  </option>
                ))}
              </select>
            </FormField>
            {selectedAgent ? (
              <div className="channel-agent-picker__meta">
                <StatusBadge tone={selectedAgent.is_published ? "success" : "warning"}>{selectedAgent.is_published ? "Published" : "Draft"}</StatusBadge>
                <span className="technical-value">{selectedAgent.agent_id}</span>
              </div>
            ) : null}
          </div>
        )}
        {selectedAgent && !selectedAgent.is_published ? (
          <p className="inline-notice inline-notice--warning">{selectedAgent.name} is a draft. Sessions start only for published agents, so publish it before going live.</p>
        ) : null}
      </section>

      <section aria-labelledby="web-step-install" className="form-panel">
        <div className="channel-step__heading">
          <span aria-hidden="true" className="channel-step__number">1</span>
          <h3 id="web-step-install">Install the SDK</h3>
        </div>
        <div className="code-block">
          <pre>{npmSnippet}</pre>
          <button className="button button--secondary" onClick={() => void handleCopy(npmSnippet, "npm")} type="button">
            {copied === "npm" ? "Copied" : "Copy command"}
          </button>
        </div>
      </section>

      <section aria-labelledby="web-step-connect" className="form-panel">
        <div className="channel-step__heading">
          <span aria-hidden="true" className="channel-step__number">2</span>
          <h3 id="web-step-connect">Connect with the client SDK</h3>
        </div>
        <p className="muted-copy">
          Browsers never hold raw API keys. Your server mints a single-use token with <code className="technical-value">/v1/session/mint</code>, and the browser passes it to <code className="technical-value">UCVEVoiceClient</code>.
        </p>
        <div className="code-block code-block--dark">
          <pre data-testid="embed-code-snippet">{scriptSnippet}</pre>
          <button className="button button--secondary" onClick={() => void handleCopy(scriptSnippet, "script")} type="button">
            {copied === "script" ? "Copied" : "Copy code"}
          </button>
        </div>
      </section>
    </div>
  );
}
