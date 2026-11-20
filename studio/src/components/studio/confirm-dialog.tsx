"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

export function ConfirmDialog({
  busy = false,
  children,
  confirmLabel,
  error,
  onCancel,
  onConfirm,
  title,
  tone = "danger",
}: {
  busy?: boolean;
  children: ReactNode;
  confirmLabel: string;
  error?: string | null;
  onCancel(): void;
  onConfirm(): void;
  title: string;
  tone?: "danger" | "primary";
}) {
  const titleId = useId();
  const descriptionId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const busyRef = useRef(busy);
  const cancelHandler = useRef(onCancel);

  useEffect(() => {
    busyRef.current = busy;
    cancelHandler.current = onCancel;
  });

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelRef.current?.focus();
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
      <div aria-describedby={descriptionId} aria-labelledby={titleId} aria-modal="true" className="studio-dialog" role="dialog">
        <h2 id={titleId}>{title}</h2>
        <div className="studio-dialog__body" id={descriptionId}>{children}</div>
        {error ? <p className="inline-notice inline-notice--danger studio-dialog__error" role="alert">{error}</p> : null}
        <div className="studio-dialog__actions">
          <button className="button button--secondary" disabled={busy} onClick={onCancel} ref={cancelRef} type="button">Cancel</button>
          <button className={`button ${tone === "danger" ? "button--danger" : "button--primary"}`} disabled={busy} onClick={onConfirm} type="button">
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
