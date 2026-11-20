import { StatePanel } from "@/components/studio/state-panel";

export interface IntegrationAgent {
  agent_id: string;
  name: string;
  is_published: boolean;
}

/**
 * What a developer needs next to an API key: which agent to mint for, and the
 * one server-side call. The API key itself selects the workspace, so no
 * workspace identifier is required in the request.
 */
export function IntegrationDetails({ agents, apiBaseUrl }: { agents: IntegrationAgent[]; apiBaseUrl: string }) {
  const published = agents.filter((agent) => agent.is_published);
  const example = published[0]?.agent_id ?? "<agent id>";
  return (
    <section aria-labelledby="integration-title" className="form-panel integration-details">
      <h2 id="integration-title">Integration details</h2>
      <p className="muted-copy">Mint a short-lived session on your server with an API key, then hand only the session token and WebSocket URL to the SDK.</p>
      {published.length === 0 ? (
        <StatePanel description="Publish an agent first; only published agents can start sessions." title="No published agents yet" />
      ) : (
        <dl className="integration-details__agents">
          {published.map((agent) => (
            <div key={agent.agent_id}>
              <dt>{agent.name}</dt>
              <dd><code className="technical-value">{agent.agent_id}</code></dd>
            </div>
          ))}
        </dl>
      )}
      <pre className="integration-details__snippet"><code>{`curl -X POST ${apiBaseUrl}/v1/session/mint \\
  -H "Authorization: Bearer $WAVIA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id": "${example}"}'`}</code></pre>
      <p className="muted-copy">The response contains <code>token</code> (single use) and <code>ws_url</code>. Keys need the <code>session:mint</code> scope.</p>
    </section>
  );
}
