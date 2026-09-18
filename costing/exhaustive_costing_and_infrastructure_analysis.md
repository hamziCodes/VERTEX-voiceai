# Wavia Voice AI — Exhaustive Costing, Infrastructure & Economics Analysis

**Product Brand:** Wavia (Wavia AI)  
**Date:** September 2026  
**Currencies & Exchange Rates Reference:**  
* **1 USD = 1.39 CAD**
* **1 USD = 278.00 PKR**

---

## 1. Executive Summary & The Voice AI Cost Stack

Wavia is a sovereign, low-latency, modular voice AI agent platform. A real-time conversational voice pipeline consists of five distinct operational cost layers:

```
[ Inbound Audio / Phone Line ] 
       ↓
[ STT: Speech-to-Text ] 
       ↓
[ LLM: Conversational Brain ] 
       ↓
[ TTS: Text-to-Speech Voice ] 
       ↓
[ Network Infrastructure & Worker Compute ]
```

### Standard Call Dynamics (1 Minute / 60 Seconds of Active Session)
* **Caller Speaking:** ~20–25 seconds of continuous stream sent to STT (~50–65 words transcribed).
* **AI Agent Speaking:** ~20–25 seconds (~500–750 text characters synthesized).
* **Pauses / Turn-taking / Endpointer:** ~10–15 seconds.
* **Conversational Turns:** ~4 to 6 request/response rounds per minute.
* **Token Usage:** ~4,000 cumulative input tokens (system prompt, conversation history, function tools) and ~200 output tokens per minute.

---

## 2. Granular Component-by-Component Cost Breakdown

### A. Speech-to-Text (Hearing Layer)

| Provider / Model | Protocol / Mechanism | Latency (TTFB) | Pricing Unit | Cost per 1 Minute | Cost per 1 Hour | Cost per 1,000 Mins |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Deepgram Nova-2** *(Default)* | Streaming WebSocket | ~150ms | $0.0043 / min | **$0.0043** | **$0.258** | **$4.30 USD** |
| **Gladia Live Real-Time** | Streaming WebSocket | ~180ms | $0.0110 / min | **$0.0110** | **$0.660** | **$11.00 USD** |
| **DeepInfra Whisper Large V3 Turbo** | HTTP Audio Chunks | ~350ms | $0.0002 / min | **$0.0002** | **$0.012** | **$0.20 USD** |

*Note: For conversational duplex voice where barge-in is required, streaming WebSockets (Deepgram Nova-2) is the industry benchmark for zero dropped packets and high accent accuracy.*

---

### B. Large Language Models (Brain Layer)

| Model & Provider | Inference Speed | Context / Reasoning | Pricing (Input / Output per 1M) | Cost per 1 Minute | Cost per 1 Hour | Cost per 1,000 Mins |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen 2.5 7B** *(DeepInfra / Groq)* | ~400 tok/sec | Fast, factual, basic logic | $0.04 / $0.06 | **$0.0002** | **$0.010** | **$0.20 USD** |
| **Google Gemini 2.0 Flash** | ~250 tok/sec | Excellent, tool calling | $0.10 / $0.40 | **$0.0005** | **$0.030** | **$0.50 USD** |
| **Groq (Llama 3.3 70B)** | ~300 tok/sec | Near-GPT-4o intelligence | $0.59 / $0.79 | **$0.0025** | **$0.150** | **$2.50 USD** |
| **OpenAI GPT-4o-mini** | ~120 tok/sec | Reliable conversational agent | $0.15 / $0.60 | **$0.0007** | **$0.042** | **$0.72 USD** |
| **OpenAI GPT-4o** | ~80 tok/sec | Complex reasoning, high nuance | $2.50 / $10.00 | **$0.0120** | **$0.720** | **$12.00 USD** |
| **Claude 3.5 Sonnet** | ~75 tok/sec | SOTA dialogue and tone | $3.00 / $15.00 | **$0.0150** | **$0.900** | **$15.00 USD** |

---

### C. Text-to-Speech (Voice Generation Layer)

| Provider / Model | Latency (TTFB) | Voice Quality / Emotion | Pricing Unit | Cost per 1 Minute (~500 chars) | Cost per 1 Hour (~30k chars) | Cost per 1,000 Mins (~500k chars) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kokoro 82M** *(via DeepInfra)* | ~120ms | Neutral, clear, pleasant | **$0.62 / 1M chars** | **$0.0003** | **$0.019** | **$0.31 USD** |
| **Deepgram Aura** | ~150ms | Conversational, direct | $0.015 / 1k chars | **$0.0075** | **$0.450** | **$7.50 USD** |
| **Cartesia Sonic** | **~90ms** | Ultra-natural, dynamic, fluid | $0.075 / 1k chars | **$0.0375** | **$2.250** | **$37.50 USD** |
| **ElevenLabs Turbo v2.5** | ~250ms | Hollywood-grade, sighs/laughs | $0.180 / 1k chars | **$0.0900** | **$5.400** | **$90.00 USD** |

---

### D. Telephony & Carrier Routing (Phone Line Layer)

| Channel | Carrier / Mechanism | Pricing Unit | Cost per 1 Hour | Cost per 1,000 Mins |
| :--- | :--- | :--- | :--- | :--- |
| **In-App / WebRTC SDK** | Direct browser / mobile WebSocket | $0.00 (Pure IP) | **$0.00** | **$0.00** |
| **Inbound Phone Calls (PSTN)** | Telnyx SIP Trunking | $0.0040 / min | **$0.240** | **$4.00 USD** |
| **Outbound Phone Calls (PSTN)** | Telnyx SIP Trunking | $0.0130 / min | **$0.780** | **$13.00 USD** |
| **Twilio Elastic SIP (Inbound)** | Twilio Trunking | $0.0045 – $0.0085 / min | **$0.270 – $0.510** | **$4.50 – $8.50 USD** |
| **Dedicated Phone Number (DID)** | Telnyx / Twilio | Monthly recurring charge | — | **$1.15 – $2.00 / mo** |

---

### E. Cloud Hosting & Server Infrastructure

Wavia’s sovereign architecture runs four core container services:
1. **Control Plane** (FastAPI REST API, agent management, JWT minting, webhook events)
2. **Worker Raw** (Asynchronous WebSocket audio ingest, duplex audio streaming, Silero VAD)
3. **Redis** (Session locks, active call routing, circuit breaker health tracking)
4. **PostgreSQL / TimescaleDB** (Call logs, audio analytics, agent configuration states)

#### Hosting Tiers:
* **Hetzner Cloud (CPX21 - 3 vCPU, 4GB RAM):** **~$12.00 – $15.00 USD / mo** (Supports 20–40 concurrent calls).
* **DigitalOcean Droplet (2 vCPU, 4GB RAM):** **~$24.00 USD / mo**.
* **AWS Lightsail / Small ECS:** **~$20.00 – $35.00 USD / mo**.
* **Cloudflare DNS + SSL:** Free ($0.00).
* **Domain Name:** ~$12.00/year (~$1.00 USD/mo).

---

## 3. Total Cost Stack for 1,000 Minutes Across Operating Profiles

### Comparison Table (USD, CAD, PKR)

| Profile | Key Stack | API Cost | Hosting | Phone Line | Total USD | Total CAD (1.39) | Total PKR (278.0) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ultra-Budget** | Deepgram + Qwen 2.5 + Kokoro | $4.81 | $15.00 | $4.00 | **$23.81** | **$33.10 CAD** | **Rs. 6,619 PKR** |
| **The Sweet Spot** | Deepgram + Gemini/Groq + Cartesia | $43.80 | $15.00 | $4.00 | **$62.80** | **$87.30 CAD** | **Rs. 17,458 PKR** |
| **Gold Standard** | Deepgram + GPT-4o + ElevenLabs | $106.30 | $15.00 | $4.00 | **$125.30** | **$174.15 CAD** | **Rs. 34,833 PKR** |

---

## 4. Wavia vs. Off-The-Shelf Ready-Made Platforms (Vapi / Retell AI)

When using an off-the-shelf voice SaaS (such as Retell AI or Vapi.ai):
* They charge a **$0.05 to $0.08 per minute platform fee** on top of all underlying models.
* For 1,000 minutes: Platform markup alone is **$50.00 to $80.00 USD**.
* Total monthly bill on Vapi/Retell for 1,000 phone minutes: **$110.00 to $150.00 USD** ($152 – $208 CAD / Rs. 30,500 – Rs. 41,700 PKR).

### Long-Term Scale Advantage of Owning Wavia

| Call Volume (Monthly Mins) | Wavia All-In Cost (USD) | Off-The-Shelf Platform Cost (USD) | Your Monthly Savings |
| :--- | :--- | :--- | :--- |
| **1,000 mins** (~16.6 hrs) | ~$63 USD | ~$125 USD | **$62 USD / mo** |
| **5,000 mins** (~83 hrs) | ~$245 USD | ~$625 USD | **$380 USD / mo** |
| **10,000 mins** (~166 hrs) | ~$460 USD | ~$1,250 USD | **$790 USD / mo** |
| **100,000 mins** (~1,666 hrs) | ~$4,350 USD | ~$12,500 USD | **$8,150 USD / mo** |

*Owning Wavia decouples your platform cost from your volume. Server hosting remains almost flat ($25–$80/mo) while SaaS middleman fees scale endlessly.*

---

## 5. Competitor Analysis: Beating the "Qwen.TTS / $0.98 per Hour" Offer

### What the Competitor Quoted:
* Retail: **$0.10 per minute** ($6.00 / hour)
* Commitment / Bulk: **$0.98 per hour** (~$0.0163 / min)

### How Wavia Beats It:
* **Deepgram Nova-2 + Qwen 2.5 7B + Kokoro 82M:**
  * STT: $0.258 / hr
  * LLM: $0.010 / hr
  * TTS: $0.019 / hr
  * Telnyx Inbound Phone: $0.240 / hr
  * **Wavia Total Direct Cost:** **$0.527 / hour** (including real phone network routing).
* **Result:** Wavia delivers real-time duplex voice at **$0.53/hr**, which is **46% cheaper than the competitor’s $0.98/hr rate**, giving you substantial room to undercut them while securing strong margins.
