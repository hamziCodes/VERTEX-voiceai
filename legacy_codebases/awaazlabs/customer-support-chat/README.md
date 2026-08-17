# AwaazLabs Customer Support

Standalone Next.js patient support chat for AwaazLabs.

## Run locally

```bash
npm install
npm run dev
```

Open the local URL printed by Next.js.

## Environment

Create `.env` locally or add these variables in Vercel:

```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

`GROQ_MODEL` is optional. The app defaults to `llama-3.3-70b-versatile`.

## Deploy to Vercel

Use the standard Vercel Next.js preset.

- Framework preset: Next.js
- Build command: `npm run build`
- Install command: `npm install`
- Output directory: leave default
- Required environment variable: `GROQ_API_KEY`

Keep `.env` private. Do not commit or share it.
