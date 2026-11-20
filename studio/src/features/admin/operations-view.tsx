import { StatusBadge } from "@/components/studio/status-badge";
import type { OperationsSignalDto, OperationsSnapshotDto } from "@/data/schema";
import { formatDateTime, formatNumber } from "@/lib/format";

const STATUS: Readonly<Record<OperationsSignalDto["status"], { label: string; tone: "success" | "warning" | "neutral" | "info" }>> = {
  healthy: { label: "Healthy", tone: "success" },
  attention: { label: "Attention", tone: "warning" },
  not_configured: { label: "Not configured", tone: "neutral" },
  disabled: { label: "Disabled", tone: "neutral" },
  not_measured: { label: "Not measured", tone: "info" },
};

const METRIC_LABELS: Readonly<Record<string, string>> = {
  queued: "Queued",
  running: "Running",
  retry_wait: "Waiting to retry",
  succeeded: "Succeeded",
  dead_letter: "Dead letter",
  latency_ms: "Latency (ms)",
  active: "Active",
};

export function OperationsView({ snapshot }: { snapshot: OperationsSnapshotDto }) {
  const attention = snapshot.signals.filter((signal) => signal.status === "attention").length;
  return (
    <div className="operations-view">
      <p className="muted-copy technical-value">Checked {formatDateTime(snapshot.checked_at)} · environment {snapshot.environment}</p>
      <p className={`inline-notice ${attention ? "inline-notice--warning" : "inline-notice--success"}`} role="status">
        {attention ? `${attention} signal${attention === 1 ? "" : "s"} need${attention === 1 ? "s" : ""} attention.` : "No signal needs attention."}
      </p>
      <p className="inline-notice inline-notice--info">
        Live provider and carrier probes do not run from the control plane, so those signals read Not measured. Readiness is not live qualification.
      </p>
      <ul aria-label="Platform signals" className="operations-grid">
        {snapshot.signals.map((signal) => {
          const status = STATUS[signal.status];
          const metrics = Object.entries(signal.metrics);
          const headingId = `signal-${signal.key}`;
          return (
            <li aria-labelledby={headingId} className="form-panel operations-signal" key={signal.key}>
              <div className="operations-signal__heading">
                <h2 className="operations-signal__title" id={headingId}>{signal.label}</h2>
                <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
              </div>
              <p className="muted-copy">{signal.detail}</p>
              {metrics.length ? (
                <dl className="operations-metrics">
                  {metrics.map(([name, value]) => (
                    <div key={name}>
                      <dt>{METRIC_LABELS[name] ?? name.replaceAll("_", " ")}</dt>
                      <dd>{formatNumber(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
