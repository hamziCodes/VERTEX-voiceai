import type { UsageDto } from "./types";

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
    <section aria-labelledby="usage-heading">
      <h2 id="usage-heading">Usage and limits</h2>
      <p>Current server-reported monthly usage. Exact period start and end dates are not supplied by the usage API.</p>
      {hardCapReached && <p role="alert">Usage hard cap reached. New sessions may be rejected until the server-reported period resets.</p>}
      <dl>
        <dt>Concurrent sessions</dt><dd>{usage.quota.current_concurrent} / {usage.quota.max_concurrent}</dd>
        <dt>Monthly minutes</dt><dd>{usage.quota.current_monthly_minutes} / {usage.quota.max_minutes_month}</dd>
        {usage.quota.max_llm_tokens_month !== undefined && (
          <><dt>Monthly LLM tokens</dt><dd>{usage.quota.current_monthly_llm_tokens ?? 0} / {usage.quota.max_llm_tokens_month}</dd></>
        )}
      </dl>
      <h3>Measured totals</h3>
      <dl>
        {Object.entries(usage.totals).map(([name, value]) => (
          <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
        ))}
      </dl>
    </section>
  );
}
