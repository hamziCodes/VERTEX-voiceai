"use client";

import { useEffect, useId, useRef, type FormEvent, type ReactNode } from "react";

export function FormDialog({
  busy = false,
  children,
  description,
  error,
  onCancel,
  onSubmit,
  submitDisabled = false,
  submitLabel,
  title,
}: {
  busy?: boolean;
  children: ReactNode;
  description?: ReactNode;
  error?: string | null;
  onCancel(): void;
  onSubmit(event: FormEvent<HTMLFormElement>): void;
  submitDisabled?: boolean;
  submitLabel: string;
  title: string;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const busyRef = useRef(busy);
  const cancelHandler = useRef(onCancel);

  useEffect(() => {
    busyRef.current = busy;
    cancelHandler.current = onCancel;
  });

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    formRef.current?.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea")?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busyRef.current) cancelHandler.current();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previous?.focus();
    };
  }, []);

  return (
    <div className="studio-dialog-backdrop">
      <div aria-describedby={description ? descriptionId : undefined} aria-labelledby={titleId} aria-modal="true" className="studio-dialog" role="dialog">
        <h2 id={titleId}>{title}</h2>
        {description ? <div className="studio-dialog__body" id={descriptionId}>{description}</div> : null}
        <form className="studio-dialog__form" noValidate onSubmit={onSubmit} ref={formRef}>
          {children}
          {error ? <p className="inline-notice inline-notice--danger studio-dialog__error" role="alert">{error}</p> : null}
          <div className="studio-dialog__actions">
            <button className="button button--secondary" disabled={busy} onClick={onCancel} type="button">Cancel</button>
            <button className="button button--primary" disabled={busy || submitDisabled} type="submit">{busy ? "Working…" : submitLabel}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
