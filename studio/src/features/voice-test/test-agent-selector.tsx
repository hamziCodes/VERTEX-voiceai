import Link from "next/link";

import { StatePanel } from "@/components/studio/state-panel";
import { StatusBadge } from "@/components/studio/status-badge";
import type { AgentDto } from "@/features/agents/types";

export function TestAgentSelector({ agents, canStart }: { agents: AgentDto[]; canStart: boolean }) {
  const sortedAgents = [...agents].sort((left, right) => left.name.localeCompare(right.name, undefined, { sensitivity: "base" }));

  if (sortedAgents.length === 0) {
    return (
      <StatePanel
        description="Create an agent, complete its configuration, and publish it before opening a voice sandbox."
        title="No agents available"
      />
    );
  }

  return (
    <div className="test-selector">
      {!canStart ? <div className="inline-notice inline-notice--info">Your role can review test readiness but cannot start a voice session.</div> : null}
      <ul aria-label="Agents available for testing" className="test-agent-list">
        {sortedAgents.map((agent) => (
          <li aria-label={agent.name} className="test-agent-row" key={agent.agent_id}>
            <span aria-hidden="true" className="test-agent-row__mark">{agent.name.slice(0, 1).toUpperCase()}</span>
            <div className="test-agent-row__copy">
              <div className="test-agent-row__title">
                <strong>{agent.name}</strong>
                <StatusBadge tone={agent.is_published ? "success" : "warning"}>{agent.is_published ? `Published · v${agent.version}` : "Draft"}</StatusBadge>
              </div>
              <p>{agent.description || "No description provided."}</p>
              {!agent.is_published ? <span className="test-agent-row__reason">Publish this agent before opening the voice sandbox.</span> : null}
            </div>
            {agent.is_published ? (
              <Link className="button button--secondary" href={`/agents/${agent.agent_id}/test`}>
                {canStart ? `Open ${agent.name} test sandbox` : `Review ${agent.name} test status`}
              </Link>
            ) : (
              <button className="button button--secondary" disabled type="button">Not ready</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
