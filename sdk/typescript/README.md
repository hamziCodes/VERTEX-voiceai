# Wavia TypeScript Voice SDK

```bash
npm install @ucve/voice-sdk   # or the tarball from a release bundle
```

Works in browsers and in Node 22+ (global `WebSocket`). The core package has
no React runtime dependency. Your backend mints the session
(`POST /v1/session/mint` with a tenant API key that has the `session:mint`
scope) and hands the client only `token` and `ws_url`:

```ts
import { SessionRejectedError, UCVEVoiceClient } from '@ucve/voice-sdk';

const client = new UCVEVoiceClient(session.token, {
  wsUrl: session.ws_url,
  onTranscript: (speaker, text) => console.log(speaker, text),
  onAudio: (pcm16) => player.enqueue(pcm16),
});
try {
  await client.connect();
} catch (error) {
  if (error instanceof SessionRejectedError) console.error(error.code, error.reason); // mint again
  throw error;
}
client.sendTextTurn('Hello');
```

A runnable example with the mint call against a local development engine is
in [`examples/quickstart.mjs`](examples/quickstart.mjs).

React users import the optional hook separately:

```ts
import { useUCVEVoice } from '@ucve/voice-sdk/react';
```

Mint the ephemeral session token in an authenticated host backend. Do not put
provider keys or mint credentials in browser code. The v1 audio wire format is
16 kHz mono PCM16.
