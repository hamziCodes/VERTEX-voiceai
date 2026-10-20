# Wavia TypeScript Voice SDK

The core package has no React runtime dependency:

```ts
import { UCVEVoiceClient } from '@ucve/voice-sdk';

const client = new UCVEVoiceClient(sessionToken, { wsUrl });
await client.connect();
client.sendTextTurn('Hello');
```

React users import the optional hook separately:

```ts
import { useUCVEVoice } from '@ucve/voice-sdk/react';
```

Mint the ephemeral session token in an authenticated host backend. Do not put
provider keys or mint credentials in browser code. The v1 audio wire format is
16 kHz mono PCM16.
