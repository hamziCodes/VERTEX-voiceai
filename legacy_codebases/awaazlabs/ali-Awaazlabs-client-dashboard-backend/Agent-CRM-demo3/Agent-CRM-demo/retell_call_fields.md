# Retell AI — Complete Call Data Fields

*Source: OpenAPI schema from `GET /v2/get-call`, `PATCH /v2/update-call`, and Webhook docs (verified July 2025).*

Fields marked **[post-call]** available after `call_ended`; **[analyzed]** after `call_analyzed`.

---

## 1. Call Identification

| Field | Type | Availability | Notes |
|---|---|---|---|
| `call_id` | string | always | Unique identifier for the call |
| `call_type` | enum | always | `phone_call` \| `web_call` |
| `agent_id` | string | always | Agent that handled the call |
| `agent_name` | string | always | Human-readable agent name |
| `agent_version` | integer | always | Version number frozen at call creation |
| `agent_tag` | string \| null | always | Environment tag (e.g. `prod`, `staging`), frozen at call creation |
| `call_status` | enum | always | `registered` \| `not_connected` \| `ongoing` \| `ended` \| `error` |
| `metadata` | object | always | Arbitrary JSON you attach at call creation (storage only, not processed, max 50kB) |
| `retell_llm_dynamic_variables` | object | always | Key-value strings injected into Response Engine prompt/tools |
| `collected_dynamic_variables` | object | [post-call] | Variables collected or updated during the call |
| `data_storage_setting` | enum \| null | always | `everything` \| `everything_except_pii` \| `basic_attributes_only` |
| `opt_in_signed_url` | boolean | always | If true, all URLs (recordings, logs) are signed and expire in 24h |
| `custom_attributes` | object | always | Custom key-value attributes set via Update Call API |

### Phone call only

| Field | Type | Notes |
|---|---|---|
| `from_number` | string | Caller's number in E.164 |
| `to_number` | string | Destination number in E.164 |
| `direction` | enum | `inbound` \| `outbound` |
| `telephony_identifier.twilio_call_sid` | string | Twilio Call SID |
| `custom_sip_headers` | object | Arbitrary SIP headers attached to the call |

### Web call only

| Field | Type | Notes |
|---|---|---|
| `access_token` | string | Room access token to pass to your frontend SDK |

---

## 2. Call Lifecycle / Timestamps

| Field | Type | Availability | Notes |
|---|---|---|---|
| `start_timestamp` | integer (ms) | after call starts | Unix epoch ms |
| `end_timestamp` | integer (ms) | [post-call] | Unix epoch ms |
| `duration_ms` | integer | [post-call] | Total call duration in milliseconds |
| `transfer_end_timestamp` | integer (ms) | [post-call] | When the transfer leg ended (if applicable) |

---

## 3. Disconnection

| Field | Type | Availability | Notes |
|---|---|---|---|
| `disconnection_reason` | enum | [post-call] | See full enum below |
| `transfer_destination` | string \| null | [post-call] | Phone number or SIP URI; only when `disconnection_reason` = `call_transfer` |

### `disconnection_reason` enum — exact API values

| Value | Meaning |
|---|---|
| `user_hangup` | Customer ended the call |
| `agent_hangup` | AI agent ended the call |
| `call_transfer` | Transferred to another destination |
| `transfer_bridged` | Transfer succeeded and bridged |
| `transfer_cancelled` | Transfer failed or was cancelled |
| `voicemail_reached` | Hit voicemail |
| `ivr_reached` | Connected to an IVR |
| `inactivity` | Ended due to inactivity timeout |
| `max_duration_reached` | Maximum call duration exceeded |
| `concurrency_limit_reached` | Too many simultaneous calls |
| `no_concurrency_fallback` | Concurrency limit hit and no fallback configured |
| `no_valid_payment` | Account payment issue |
| `scam_detected` | Terminated by scam detection |
| `dial_busy` | Destination was busy |
| `dial_failed` | Dial failed (generic) |
| `dial_no_answer` | No answer |
| `invalid_destination` | Invalid destination number or URI |
| `telephony_provider_permission_denied` | Provider rejected due to permissions |
| `telephony_provider_unavailable` | Provider was unavailable |
| `sip_routing_error` | SIP routing failure |
| `marked_as_spam` | Flagged as spam |
| `user_declined` | User rejected the incoming call |
| `manual_stopped` | Manually terminated via API |
| `call_take_over` | Human agent took over the call |
| `registered_call_timeout` | Call was registered but never connected |
| `error_llm_websocket_open` | LLM WebSocket failed to open |
| `error_llm_websocket_lost_connection` | LLM WebSocket dropped mid-call |
| `error_llm_websocket_runtime` | LLM WebSocket runtime error |
| `error_llm_websocket_corrupt_payload` | LLM WebSocket returned corrupt data |
| `error_no_audio_received` | No audio received from user |
| `error_asr` | Speech recognition failure |
| `error_retell` | Internal Retell platform error |
| `error_unknown` | Unknown error |
| `error_user_not_joined` | Web call — user never joined the room |

---

## 4. Transcript

### Top-level transcript fields

| Field | Availability | Notes |
|---|---|---|
| `transcript` | [post-call] | Full conversation as plain text |
| `transcript_object[]` | [post-call] | Utterances with speaker labels and word timestamps |
| `transcript_with_tool_calls[]` | [post-call] | Full event log including tool calls and system events |
| `scrubbed_transcript_with_tool_calls[]` | [post-call] | PII-redacted version of `transcript_with_tool_calls` |

### Utterance schema (used in `transcript_object`)

| Field | Type | Notes |
|---|---|---|
| `role` | enum | `agent` \| `user` \| `transfer_target` |
| `content` | string | Text of the utterance |
| `words[]` | array | Per-word breakdown (see below) |
| `words[].word` | string | Word text (with punctuation) |
| `words[].start` | number | Start time in seconds relative to call start (approximate) |
| `words[].end` | number | End time in seconds relative to call start (approximate) |

### UtteranceOrToolCall types (used in `transcript_with_tool_calls`)

`agent` / `user` / `transfer_target` — same schema as Utterance above.

#### `tool_call_invocation`

| Field | Type | Notes |
|---|---|---|
| `role` | `"tool_call_invocation"` | |
| `tool_call_id` | string | Globally unique ID |
| `name` | string | Function name |
| `arguments` | string | Stringified JSON of arguments |
| `thought_signature` | string | Optional — Gemini thinking model reasoning chain (internal use) |

#### `tool_call_result`

| Field | Type | Notes |
|---|---|---|
| `role` | `"tool_call_result"` | |
| `tool_call_id` | string | Matches the invocation |
| `content` | string | Result string or stringified JSON |
| `successful` | boolean | Whether the tool call succeeded |

#### `node_transition` (Conversation Flow agents only)

| Field | Type | Notes |
|---|---|---|
| `role` | `"node_transition"` | |
| `former_node_id` | string | |
| `former_node_name` | string | |
| `new_node_id` | string | |
| `new_node_name` | string | |
| `transition_type` | enum | `global` \| `global_go_back` \| `interrupt_go_back` \| `normal` |

#### `dtmf` (keypad input)

| Field | Type | Notes |
|---|---|---|
| `role` | `"dtmf"` | |
| `digit` | string | Single character: `"0"`–`"9"`, `"*"`, `"#"` |

#### `sms` (SMS received during call)

| Field | Type | Notes |
|---|---|---|
| `role` | `"sms"` | |
| `content` | string | Text content of the SMS |
| `multimedia[]` | array | MMS attachments (display only, not relayed into conversation) |
| `multimedia[].url` | string | URL of the attachment |
| `multimedia[].summary` | string | Optional text summary of the attachment |
| `time_sec` | number | Seconds since call start when SMS was received |

#### `injected` (mid-call context injection)

| Field | Type | Notes |
|---|---|---|
| `role` | `"injected"` | |
| `content` | string | The injected context text |
| `time_sec` | number | Seconds since call start when injection occurred |

---

## 5. Audio & Recordings

| Field | Availability | Notes |
|---|---|---|
| `recording_url` | [post-call] | Mono recording (`.wav`) |
| `recording_multi_channel_url` | [post-call] | Separate channels for agent and user |
| `scrubbed_recording_url` | [post-call] | PII-redacted mono recording |
| `scrubbed_recording_multi_channel_url` | [post-call] | PII-redacted multi-channel recording |

> URLs are signed and expire in 24h when `opt_in_signed_url = true`.

---

## 6. Latency

All under the `latency` object. Not all fields present — depends on call type and features used.

Every latency metric uses the `CallLatency` schema:

| Sub-field | Notes |
|---|---|
| `p50, p90, p95, p99` | Percentile values in ms |
| `max, min` | Extremes in ms |
| `num` | Number of data points |
| `values[]` | Array of all individual measurements in ms |

### Latency metrics

| Key | Notes |
|---|---|
| `latency.e2e` | End-to-end: from user stops talking → agent starts talking (excludes network trip to frontend) |
| `latency.asr` | ASR transcription latency (chunk stream duration vs transcribed duration delta) |
| `latency.llm` | LLM latency: from LLM call issued → first speakable chunk received (includes WebSocket RTT for custom LLM) |
| `latency.llm_websocket_network_rtt` | WebSocket RTT between your server and Retell server — custom LLM only |
| `latency.tts` | TTS latency: from TTS triggered → first audio byte received |
| `latency.knowledge_base` | KB retrieval time — only when KB feature is used |
| `latency.s2s` | Speech-to-speech: from S2S model request → first byte — Realtime API / S2S models only |

---

## 7. Post-Call Analysis

Available after `call_analyzed` webhook fires. All fields under `call_analysis`.

| Field | Type | Notes |
|---|---|---|
| `call_analysis.call_summary` | string | AI-generated call summary |
| `call_analysis.in_voicemail` | boolean | Whether the call hit voicemail |
| `call_analysis.user_sentiment` | enum | `Positive` \| `Negative` \| `Neutral` \| `Unknown` |
| `call_analysis.call_successful` | boolean | Whether agent completed its task without being cut off |
| `call_analysis.custom_analysis_data` | object | Your defined extraction fields (strings, enums, booleans, numbers) |

---

## 8. Call Cost

All under the `call_cost` object.

| Field | Type | Notes |
|---|---|---|
| `call_cost.combined_cost` | number | Total cost in cents |
| `call_cost.total_duration_seconds` | number | Billable call duration in seconds |
| `call_cost.total_duration_unit_price` | number | Combined per-second price across all products (cents/sec) |
| `call_cost.product_costs[]` | array | Itemized cost per product (see below) |

### `ProductCost` schema

| Field | Type | Notes |
|---|---|---|
| `product` | string | Product name e.g. `elevenlabs_tts`, `deepgram_asr`, `retell_llm`, `telephony` |
| `unit_price` | number | Cents per second for this product |
| `cost` | number | Total cost for this product for this call in cents |
| `is_transfer_leg_cost` | boolean | `true` if this cost item is for a transfer leg |

---

## 9. LLM Token Usage

Under `llm_token_usage`. Not populated for custom LLM, Realtime API, or when no LLM call is made.

| Field | Type | Notes |
|---|---|---|
| `llm_token_usage.values[]` | array of number | Per-request token counts |
| `llm_token_usage.average` | number | Average tokens per request |
| `llm_token_usage.num_requests` | number | Number of LLM requests made during the call |

---

## 10. Debugging

| Field | Availability | Notes |
|---|---|---|
| `public_log_url` | [post-call] | Full debug log: all LLM WebSocket requests/responses, latency per turn, tracing |
| `knowledge_base_retrieved_contents_url` | [post-call] | S3 URL to `.txt` file mapping `respond_id` → retrieved KB chunks. Only present when KB feature was used |
| PCAP download | dashboard only | Packet capture file available in call details page for network/audio debugging (Wireshark) |

---

## 11. Webhook Events

### Voice call events

| Event | Fires when | Payload extras |
|---|---|---|
| `call_started` | Call connects (not fired on `dial_failed` / `dial_no_answer` / `dial_busy`) | Basic call object |
| `call_ended` | Call ends | Full call object minus `call_analysis` |
| `call_analyzed` | Post-call analysis completes | Full call object including `call_analysis` |
| `transcript_updated` | Every turn during the call + once on call end | Full call object + `transcript_with_tool_calls`; treat as incremental |
| `transfer_started` | Transfer attempt begins | Call object + `transfer_destination` + `transfer_option` |
| `transfer_bridged` | Transfer successfully bridges | Call object + `transfer_destination` + `transfer_option` |
| `transfer_cancelled` | Transfer fails or is cancelled | Call object + `transfer_destination` + `transfer_option` |
| `transfer_ended` | Transfer leg ends | Full call object |

### `transfer_option` fields (present on transfer events when available)

| Field | Notes |
|---|---|
| `type` | `cold_transfer` \| `warm_transfer` |
| `showTransfereeAsCaller` | boolean |
| `publicHandoffOption` | Object with `type` and optional `message` |
| `agentDetectionTimeoutMs` | integer |
| `onHoldMusic` | Object with `type` |
| `enableBridgeAudioCue` | boolean |

### Chat agent events

| Event | Fires when |
|---|---|
| `chat_started` | Chat session begins |
| `chat_ended` | Chat session ends |
| `chat_analyzed` | Post-chat analysis completes |

### Webhook delivery

- **Timeout:** 10 seconds, retried up to 3 times on non-2xx
- **Not blocking:** later events fire even if earlier ones failed
- **Allowlist IP:** `100.20.5.228`
- **Verify signature** via `x-retell-signature` header + your API key
- **Default events per agent:** `call_started`, `call_ended`, `call_analyzed` (configurable via `webhook_events` agent field)
- **Webhook URLs support dynamic variables** e.g. `https://example.com/webhook?id={{customer_id}}`

### Idempotency keys

| Event type | Key |
|---|---|
| `call_started`, `call_ended`, `call_analyzed` | `event` + `call_id` (fires once per call) |
| `transfer_*` | `event` + `call_id` + `start_timestamp` (multiple per call possible) |
| `transcript_updated` | No dedup — store latest payload per `call_id` |

---

## 12. Update Call API (`PATCH /v2/update-call/{call_id}`)

Fields you can write on an existing call (ongoing or ended):

| Field | Notes |
|---|---|
| `metadata` | Overwrite arbitrary storage object (max 50kB) |
| `data_storage_setting` | Can only be made more restrictive, never less |
| `custom_attributes` | Set/update custom key-value attributes (string, number, or boolean values) |
| `override_dynamic_variables` | Deprecated — use `/v2/update-livecall` instead |



Additional live time transcription : 
If you are building your own user interface and want to display the text as the customer is actively speaking, you can use Retell's client SDK.How it works: You integrate the Retell Web or mobile SDK into your platform. The SDK emits real-time events that include exactly what the agent and the user are saying, allowing you to build a live-scrolling transcript window directly into your CRM or app.Reference: View the Retell Connect to Web Call Guide for implementation steps.2. Live Agent Monitoring (Retell Dashboard)If you do not want to build a custom integration from scratch but still need third parties or your team to view calls live, you can use Retell's native Live Monitoring.How it works: You can assign permissions for team members to monitor ongoing calls on the Retell Dashboard. They can click into active calls to view live transcripts and listen in (without the customer or AI agent being aware).Reference: Learn more via the Retell Live Monitoring Documentation.