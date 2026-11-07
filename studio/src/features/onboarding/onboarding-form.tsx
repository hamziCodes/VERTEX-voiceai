"use client";

import { useState, type FormEvent } from "react";

import { FormField } from "@/components/studio/form-field";

export interface OnboardingValues {
  business_name: string;
  use_case: string;
  languages: string[];
  operating_region: string;
  timezone: string;
  escalation_email: string | null;
  completed_steps: string[];
}

const REQUIREMENT_LABELS: Readonly<Record<string, string>> = {
  business_name_required: "Business name is required.",
  use_case_required: "Use case is required.",
  operating_region_required: "Operating region is required.",
};

export function OnboardingForm({
  initial,
  requirementCodes,
  canEdit,
  saveAction,
}: {
  initial: OnboardingValues;
  requirementCodes: string[];
  canEdit: boolean;
  saveAction(values: OnboardingValues): Promise<{ state: "saved" | "error"; message?: string }>;
}) {
  const [values, setValues] = useState(initial);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [message, setMessage] = useState("");

  function update(name: keyof OnboardingValues, value: string | string[]) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEdit) return;
    setStatus("saving");
    const result = await saveAction({ ...values, completed_steps: ["business", "use_case", "languages", "region"] });
    setStatus(result.state);
    setMessage(result.message ?? "");
  }

  const statusMessage = status === "saving"
    ? "Saving onboarding…"
    : status === "saved"
      ? "Onboarding saved."
      : status === "error"
        ? message || "Onboarding could not be saved."
        : "";

  return (
    <form className="guided-form" onSubmit={submit}>
      {!canEdit ? <div className="inline-notice inline-notice--info"><strong>You have view-only access.</strong> <span>Workspace editors can update these details.</span></div> : null}
      {requirementCodes.length > 0 ? (
        <section aria-label="Remaining setup" className="setup-requirements">
          <p className="screen-eyebrow">Required before launch</p>
          <h2>Still needed</h2>
          <ul>{requirementCodes.map((code) => <li key={code}>{REQUIREMENT_LABELS[code] ?? "Complete this setup item."}</li>)}</ul>
        </section>
      ) : null}
      <section className="form-panel">
        <div className="panel-heading">
          <p className="screen-eyebrow">Business profile</p>
          <h2>How this workspace operates</h2>
          <p>These details help keep agent setup consistent across your team.</p>
        </div>
        <div className="field-grid">
          <FormField label="Business name" name="business-name">
            <input autoComplete="organization" disabled={!canEdit} value={values.business_name} onChange={(event) => update("business_name", event.target.value)} />
          </FormField>
          <FormField label="Primary use case" name="primary-use-case">
            <select disabled={!canEdit} value={values.use_case} onChange={(event) => update("use_case", event.target.value)}>
              <option value="">Choose a use case</option>
              <option value="customer_support">Customer support</option>
              <option value="lead_qualification">Lead qualification</option>
              <option value="appointments">Appointments</option>
              <option value="other">Other</option>
            </select>
          </FormField>
          <FormField hint="Use comma-separated language codes, for example: en, ur." label="Languages" name="languages">
            <input disabled={!canEdit} value={values.languages.join(", ")} onChange={(event) => update("languages", event.target.value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean))} />
          </FormField>
          <FormField label="Operating region" name="operating-region">
            <input disabled={!canEdit} value={values.operating_region} onChange={(event) => update("operating_region", event.target.value)} />
          </FormField>
          <FormField hint="Use an IANA timezone such as Asia/Karachi." label="Timezone" name="timezone">
            <input disabled={!canEdit} value={values.timezone} onChange={(event) => update("timezone", event.target.value)} />
          </FormField>
          <FormField hint="Optional. Used when an agent needs to hand a conversation to your team." label="Escalation email" name="escalation-email">
            <input autoComplete="email" disabled={!canEdit} type="email" value={values.escalation_email ?? ""} onChange={(event) => update("escalation_email", event.target.value)} />
          </FormField>
        </div>
      </section>
      <div className="guided-form__actions">
        <div aria-live="polite" className="guided-form__status" role={status === "error" ? "alert" : statusMessage ? "status" : undefined}>
          {statusMessage}
        </div>
        <button className="button button--primary" disabled={!canEdit || status === "saving"} type="submit">
          {status === "saving" ? "Saving…" : "Save and continue"}
        </button>
      </div>
    </form>
  );
}
