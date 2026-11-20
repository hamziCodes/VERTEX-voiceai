import type { ReactNode } from "react";

type StateTone = "empty" | "error" | "loading" | "info";

const MARKS: Record<StateTone, string> = {
  empty: "—",
  error: "!",
  loading: "…",
  info: "i",
};

export function StatePanel({
  actions,
  description,
  title,
  tone = "empty",
}: {
  actions?: ReactNode;
  description: string;
  title: string;
  tone?: StateTone;
}) {
  const liveRole = tone === "error" ? "alert" : tone === "loading" ? "status" : undefined;
  return (
    <section aria-busy={tone === "loading" ? true : undefined} className={`state-card state-card--${tone}`} role={liveRole}>
      <span aria-hidden="true" className="state-card__mark">{MARKS[tone]}</span>
      <div className="state-card__copy">
        <h2>{title}</h2>
        <p>{description}</p>
        {actions ? <div className="state-card__actions">{actions}</div> : null}
      </div>
    </section>
  );
}
