# UCVE Data Classification Dictionary

| Artifact Type | Field Path | Data Class | Sensitivity | Description |
|---|---|---|---|---|
| `raw_audio` | `pcm_bytes` | `phi` | Critical | Raw 16kHz PCM audio stream |
| `transcript_turn` | `text` | `phi` | High | Speech-to-text transcript hypothesis |
| `recording_object` | `s3_uri` | `phi` | High | Storage pointer to recorded audio |
| `llm_prompt` | `messages` | `phi` | High | Conversation prompt history |
| `llm_response` | `text` | `phi` | High | Generated agent response text |
| `extraction_output` | `fields` | `pii` | Medium | Post-call structured JSON entities |
| `usage_event` | `quantity` | `internal` | Low | Metering call duration & token counts |
| `audit_log` | `actor` | `audit` | High | System access & credential resolve events |
| `provider_payload` | `headers` | `pii` | Medium | Provider HTTP request/response payloads |
