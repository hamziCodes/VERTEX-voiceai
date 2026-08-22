import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

type PhaseStatus = "Pass" | "Needs Fix" | "Incomplete";

const PHASE_ROWS: {
  phase: string;
  status: PhaseStatus;
  focus: string;
  critical: number;
  high: number;
  medium: number;
}[] = [
  {
    phase: "18",
    status: "Incomplete",
    focus: "Telephony/SIP base (Telnyx + DirectSIP)",
    critical: 7,
    high: 7,
    medium: 6,
  },
  {
    phase: "19",
    status: "Needs Fix",
    focus: "Trunk abstraction & failover",
    critical: 3,
    high: 3,
    medium: 5,
  },
  {
    phase: "20",
    status: "Incomplete",
    focus: "Post-call CallRecord schema",
    critical: 6,
    high: 6,
    medium: 6,
  },
  {
    phase: "21",
    status: "Incomplete",
    focus: "Extraction & CRM dispatch",
    critical: 6,
    high: 6,
    medium: 8,
  },
  {
    phase: "22",
    status: "Incomplete",
    focus: "MCP tooling layer",
    critical: 6,
    high: 6,
    medium: 6,
  },
  {
    phase: "23",
    status: "Incomplete",
    focus: "RAG / pgvector / ingestion",
    critical: 7,
    high: 7,
    medium: 5,
  },
  {
    phase: "24",
    status: "Needs Fix",
    focus: "Latency SLO & demotion",
    critical: 6,
    high: 6,
    medium: 4,
  },
  {
    phase: "25",
    status: "Needs Fix",
    focus: "Error taxonomy & alerting",
    critical: 7,
    high: 7,
    medium: 6,
  },
];

const BLOCKER_THEMES = [
  {
    title: "Cross-phase wiring absent",
    detail:
      "Phase 17 PipelineOrchestrator never receives telephony frames, MCP tools, RAG context, latency hooks, or post-call enqueue.",
  },
  {
    title: "Security fail-open paths",
    detail:
      "Telnyx signature HMAC fallback on public key; webhook key optional; DID resolver defaults to a shared tenant; unmounted control-plane routes.",
  },
  {
    title: "Persistence is in-memory",
    detail:
      "CallRecord repo, HumanReviewQueue, MCP/RAG stores, and DLQ ignore Postgres migrations; several tables lack RLS.",
  },
  {
    title: "Declared behavior not implemented",
    detail:
      "Webhook 3x backoff, AlertRouter email/webhook, pgvector retrieve, MCP transports, and rolling-p50 demotion are stubs or no-ops.",
  },
];

const REMEDIATION_WAVES = [
  {
    wave: "Wave A — Security & admission",
    items:
      "Fix Telnyx verify (Ed25519-only or separate HMAC secret); fail-closed when key unset; reject unknown DIDs; mount+auth telephony routes.",
    tone: "deleted" as const,
  },
  {
    wave: "Wave B — Pipeline bridges",
    items:
      "Wire DirectSIP to AudioFrame to PipelineOrchestrator; emit telephony_sec; inject MCP/RAG/latency hooks; enqueue PostCallPipeline on disconnect.",
    tone: "warning" as const,
  },
  {
    wave: "Wave C — Persistence & isolation",
    items:
      "Real SQL repos for call_records / DLQ / review queue; embedding column + RLS on knowledge_chunks; vault-backed secrets for trunks/MCP/webhooks.",
    tone: "warning" as const,
  },
  {
    wave: "Wave D — Dispatch & ops",
    items:
      "HTTP webhook with retries/idempotency/DLQ; AlertRouter SMTP+HMAC webhook + Phase 07/12; SLO demotion to FailoverRouter; deepen section 7 tests.",
    tone: "info" as const,
  },
];

export default function Phases1825ProductionAudit() {
  const incomplete = PHASE_ROWS.filter((r) => r.status === "Incomplete").length;
  const needsFix = PHASE_ROWS.filter((r) => r.status === "Needs Fix").length;
  const totalCritical = PHASE_ROWS.reduce((s, r) => s + r.critical, 0);

  return (
    <Stack gap={24} style={{ padding: 24, maxWidth: 1100 }}>
      <Stack gap={8}>
        <H1>Phases 18–25 Production Readiness Audit</H1>
        <Text tone="secondary" size="small">
          Source: phase specs §3/§7 vs implementation under telephony_gateway/,
          post_call/, core/, worker_raw/, control_plane/, infra/db/migrations.
          Tracker claims COMPLETED for all eight phases (2026-08-22).
        </Text>
      </Stack>

      <Callout tone="danger">
        None of Phases 18–25 are production-ready. Tracker COMPLETED status
        overstates readiness: deliverable files exist, but exit criteria,
        security fail-closed paths, and Phase 17 integration are largely unmet.
        Phase tests mostly assert surface shape, not §7 deep contracts.
      </Callout>

      <Grid columns={4} gap={16}>
        <Stat value="0 / 8" label="Phases Pass" tone="danger" />
        <Stat value={String(incomplete)} label="Incomplete" tone="danger" />
        <Stat value={String(needsFix)} label="Needs Fix" tone="warning" />
        <Stat
          value={String(totalCritical)}
          label="High-severity findings"
          tone="danger"
        />
      </Grid>

      <Stack gap={8}>
        <H2>Phase status matrix</H2>
        <Table
          headers={[
            "Phase",
            "Status",
            "Core functionality checked",
            "Critical findings",
          ]}
          columnAlign={["left", "left", "left", "right"]}
          rows={PHASE_ROWS.map((r) => [
            `Phase ${r.phase}`,
            r.status,
            r.focus,
            String(r.critical),
          ])}
          rowTone={PHASE_ROWS.map((r) =>
            r.status === "Incomplete" ? "danger" : "warning",
          )}
        />
      </Stack>

      <Stack gap={8}>
        <H2>Findings by phase (severity counts)</H2>
        <BarChart
          categories={PHASE_ROWS.map((r) => `P${r.phase}`)}
          series={[
            {
              name: "High-severity count",
              data: PHASE_ROWS.map((r) => r.high),
              tone: "danger",
            },
            {
              name: "Medium-severity count",
              data: PHASE_ROWS.map((r) => r.medium),
              tone: "warning",
            },
          ]}
          height={220}
        />
        <Text tone="secondary" size="small">
          Counts are distinct High/Medium anomalies from the detailed audit.
        </Text>
      </Stack>

      <Divider />

      <Stack gap={12}>
        <H2>Systemic blocker themes</H2>
        <Grid columns={2} gap={12}>
          <Card>
            <CardHeader>
              <Text weight="semibold">{BLOCKER_THEMES[0].title}</Text>
            </CardHeader>
            <CardBody>
              <Text size="small">{BLOCKER_THEMES[0].detail}</Text>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <Text weight="semibold">{BLOCKER_THEMES[1].title}</Text>
            </CardHeader>
            <CardBody>
              <Text size="small">{BLOCKER_THEMES[1].detail}</Text>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <Text weight="semibold">{BLOCKER_THEMES[2].title}</Text>
            </CardHeader>
            <CardBody>
              <Text size="small">{BLOCKER_THEMES[2].detail}</Text>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <Text weight="semibold">{BLOCKER_THEMES[3].title}</Text>
            </CardHeader>
            <CardBody>
              <Text size="small">{BLOCKER_THEMES[3].detail}</Text>
            </CardBody>
          </Card>
        </Grid>
      </Stack>

      <Stack gap={12}>
        <H2>Highest-impact anomalies</H2>
        <Table
          headers={["Phase", "Component", "Gap", "Severity"]}
          columnAlign={["left", "left", "left", "left"]}
          rows={[
            [
              "18",
              "signature.py / webhook.py",
              "Ed25519 failure falls through to HMAC using public key; empty key skips verify",
              "High",
            ],
            [
              "18",
              "inbound_handler.py",
              "No PipelineOrchestrator / AudioFrame / telephony_sec metering",
              "High",
            ],
            [
              "18–25",
              "control_plane/app.py",
              "telephony, extraction, knowledge, alerts routers never mounted",
              "High",
            ],
            [
              "20",
              "call_record_repo.py",
              "PostgresCallRecordRepository is dict-only; Phase 17 never enqueues",
              "High",
            ],
            [
              "21",
              "webhook/dispatcher.py",
              "No HTTP retry/backoff/idempotency; default path always returns True",
              "High",
            ],
            [
              "22",
              "mcp/host.py",
              "Mock connect/list/call; vault unused; FSM/pipeline unwired",
              "High",
            ],
            [
              "23",
              "013_knowledge_base_pgvector.sql",
              "No embedding column, HNSW, or RLS; retriever is keyword mock",
              "High",
            ],
            [
              "24",
              "latency/demotion.py",
              "Consecutive-turn counter, not rolling p50; no FailoverRouter write",
              "High",
            ],
            [
              "25",
              "alert_router.py / dlq.py",
              "Email/webhook stubs; DLQ in-memory; quota soft-warn unwired",
              "High",
            ],
          ]}
          rowTone={[
            "danger",
            "danger",
            "danger",
            "danger",
            "danger",
            "danger",
            "danger",
            "danger",
            "danger",
          ]}
        />
      </Stack>

      <Divider />

      <Stack gap={12}>
        <H2>Remediation plan (ordered)</H2>
        <Row gap={12} align="start">
          <Pill tone={REMEDIATION_WAVES[0].tone} size="sm">
            1
          </Pill>
          <Stack gap={4} style={{ flex: 1 }}>
            <Text weight="semibold">{REMEDIATION_WAVES[0].wave}</Text>
            <Text size="small" tone="secondary">
              {REMEDIATION_WAVES[0].items}
            </Text>
          </Stack>
        </Row>
        <Row gap={12} align="start">
          <Pill tone={REMEDIATION_WAVES[1].tone} size="sm">
            2
          </Pill>
          <Stack gap={4} style={{ flex: 1 }}>
            <Text weight="semibold">{REMEDIATION_WAVES[1].wave}</Text>
            <Text size="small" tone="secondary">
              {REMEDIATION_WAVES[1].items}
            </Text>
          </Stack>
        </Row>
        <Row gap={12} align="start">
          <Pill tone={REMEDIATION_WAVES[2].tone} size="sm">
            3
          </Pill>
          <Stack gap={4} style={{ flex: 1 }}>
            <Text weight="semibold">{REMEDIATION_WAVES[2].wave}</Text>
            <Text size="small" tone="secondary">
              {REMEDIATION_WAVES[2].items}
            </Text>
          </Stack>
        </Row>
        <Row gap={12} align="start">
          <Pill tone={REMEDIATION_WAVES[3].tone} size="sm">
            4
          </Pill>
          <Stack gap={4} style={{ flex: 1 }}>
            <Text weight="semibold">{REMEDIATION_WAVES[3].wave}</Text>
            <Text size="small" tone="secondary">
              {REMEDIATION_WAVES[3].items}
            </Text>
          </Stack>
        </Row>
      </Stack>

      <Stack gap={8}>
        <H2>Verification protocol (summary)</H2>
        <H3>Per-phase pytest</H3>
        <Code>
          python -m pytest voice_engine_plan/tests/phase_tests/test_phase_18_*.py
          voice_engine_plan/tests/phase_tests/test_phase_19_*.py
          voice_engine_plan/tests/phase_tests/test_phase_20_*.py
          voice_engine_plan/tests/phase_tests/test_phase_21_*.py
          voice_engine_plan/tests/phase_tests/test_phase_22_*.py
          voice_engine_plan/tests/phase_tests/test_phase_23_*.py
          voice_engine_plan/tests/phase_tests/test_phase_24_*.py
          voice_engine_plan/tests/phase_tests/test_phase_25_*.py -v
        </Code>
        <Spacer height={8} />
        <H3>Must-add integration assertions before deploy</H3>
        <Text size="small">
          Invalid Telnyx signature rejected with key set; unknown DID rejected;
          inbound mulaw completes one PipelineOrchestrator turn; telephony_sec
          recorded; CallRecord persisted via SQL ON CONFLICT; webhook HMAC
          verified by mock receiver with 3 retries then DLQ; MCP timeout drives
          TTS fallback plus audit; pgvector RLS blocks cross-tenant; demotion
          updates FailoverRouter when enforce_demotion=true; AlertRouter fires
          on LATENCY_SLO_BREACH and quota soft-warn.
        </Text>
        <Spacer height={8} />
        <Code>python voice_engine_plan/scripts/verify_plan_integrity.py</Code>
      </Stack>

      <Callout tone="warning">
        Do not treat EXECUTION_TRACKER COMPLETED for 18–25 as a production gate.
        Re-open those rows to IN_PROGRESS until Wave A–D exit criteria and
        deepened §7 tests pass.
      </Callout>
    </Stack>
  );
}
