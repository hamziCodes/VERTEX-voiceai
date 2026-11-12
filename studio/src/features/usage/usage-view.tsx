import { formatNumber } from "@/lib/format";
import { humanize } from "@/features/operations/labels";

import type { UsageDto } from "./types";

const TOTAL_LABELS: Readonly<Record<string, string>> = {
  stt_sec: "Speech-to-text seconds",
  tts_sec: "Text-to-speech seconds",
  llm_tokens: "LLM tokens",
  agent_sec: "Agent seconds",
  telephony_sec: "Telephony seconds",
};

function UsageMeter({ label, current, max }: { label: string; current: number; max: number }) {
  const text = `${formatNumber(current)} of ${formatNumber(max)}`;
  return (
    <div className="usage-meter">
      <div className="usage-meter__label">
        <span>{label}</span>
        <span className="technical-value">{text}</span>
      </div>
      <meter
        aria-label={label}
        aria-valuemax={max}
        aria-valuemin={0}
        aria-valuenow={current}
        aria-valuetext={text}
        max={max > 0 ? max : 1}
        min={0}
        value={current}
      />
    </div>
  );
}

export function UsageView({ usage }: { usage: UsageDto }) {
  const minutePercent = usage.quota.max_minutes_month > 0
    ? (usage.quota.current_monthly_minutes / usage.quota.max_minutes_month) * 100
    : 0;
  const tokenPercent = (usage.quota.max_llm_tokens_month ?? 0) > 0
    ? ((usage.quota.current_monthly_llm_tokens ?? 0) / (usage.quota.max_llm_tokens_month ?? 1)) * 100
    : 0;
  const hardCap = usage.quota.hard_cap_percent ?? 100;
  const hardCapReached = minutePercent >= hardCap || tokenPercent >= hardCap;

  return (
    <div className="usage-view">
      {hardCapReached ? <p className="inline-notice inline-notice--danger" role="alert">Usage hard cap reached. New sessions may be rejected until the server-reported period resets.</p> : null}
      <section aria-labelledby="usage-limits-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="usage-limits-heading">Current limits</h2>
        <p className="muted-copy">Current server-reported monthly usage. Exact period start and end dates are not supplied by the usage API.</p>
        <div className="usage-meters">
          <UsageMeter current={usage.quota.current_concurrent} label="Concurrent sessions" max={usage.quota.max_concurrent} />
          <UsageMeter current={usage.quota.current_monthly_minutes} label="Monthly minutes" max={usage.quota.max_minutes_month} />
          {usage.quota.max_llm_tokens_month !== undefined ? (
            <UsageMeter current={usage.quota.current_monthly_llm_tokens ?? 0} label="Monthly LLM tokens" max={usage.quota.max_llm_tokens_month} />
          ) : null}
        </div>
      </section>
      <section aria-labelledby="usage-totals-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="usage-totals-heading">Measured totals</h2>
        <dl className="detail-grid">
          {Object.entries(usage.totals).map(([name, value]) => (
            <div key={name}><dt>{TOTAL_LABELS[name] ?? humanize(name)}</dt><dd className="technical-value">{formatNumber(value)}</dd></div>
          ))}
        </dl>
      </section>
    </div>
  );
}
