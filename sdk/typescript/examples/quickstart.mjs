// Wavia TypeScript SDK quickstart (Node 22+ or any browser): mint a session,
// say hello, hear the agent.
//
//   npm install @ucve/voice-sdk
//   node quickstart.mjs http://127.0.0.1:8000
//
// The mint call is shown inline for a local demo-mode engine. In production
// it belongs in your authenticated backend (tenant API key with the
// `session:mint` scope); the client only ever receives the session token.
import { UCVEVoiceClient } from '@ucve/voice-sdk';

const controlPlane = process.argv[2] || 'http://127.0.0.1:8000';
const wsOverride = process.argv[3];

// With an API key (WAVIA_API_KEY) the key selects the workspace; pass the
// agent ID shown in Studio > API keys > Integration details. Without a key
// this targets a local development engine's demo tenant and agent.
const apiKey = process.env.WAVIA_API_KEY;
const agentId = process.env.WAVIA_AGENT_ID || '00000000-0000-0000-0000-0000000000a1';
const minted = await fetch(`${controlPlane.replace(/\/$/, '')}/v1/session/mint`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
  },
  body: JSON.stringify(apiKey ? { agent_id: agentId } : { tenant_id: '00000000-0000-0000-0000-000000000001', agent_id: agentId }),
});
if (!minted.ok) throw new Error(`mint failed: HTTP ${minted.status}`);
const session = await minted.json();

let samples = 0;
let resolveReply;
const replied = new Promise((resolve) => { resolveReply = resolve; });

const client = new UCVEVoiceClient(session.token, {
  wsUrl: wsOverride || session.ws_url,
  onTranscript: (speaker, text) => { if (speaker === 'agent' && text) console.log(`agent: ${text}`); },
  onAudio: (pcm16) => {
    samples += pcm16.length;
    if (samples >= 1600) resolveReply(); // 100 ms at 16 kHz
  },
  onError: (err) => console.error(`error: ${err.message}`),
});

await client.connect();
client.sendTextTurn('Hello, what can you help me with?');
const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('no agent audio before the timeout')), 20000));
try {
  await Promise.race([replied, timeout]);
  console.log(`received ${samples * 2} bytes of agent audio`);
} finally {
  client.disconnect();
}
process.exit(0);
