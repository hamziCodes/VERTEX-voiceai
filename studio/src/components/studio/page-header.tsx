import type { ReactNode } from "react";

export function PageHeader({
  actions,
  eyebrow,
  summary,
  title,
}: {
  actions?: ReactNode;
  eyebrow?: string;
  summary?: string;
  title: string;
}) {
  return (
    <header className="page-header">
      <div className="page-header__copy">
        {eyebrow ? <p className="screen-eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {summary ? <p className="page-header__summary">{summary}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}
