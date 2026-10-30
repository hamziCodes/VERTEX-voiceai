"use client";

import { useState, type FormEvent } from "react";

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

  return (
    <form onSubmit={submit}>
      {!canEdit ? <p>You have view-only access.</p> : null}
      {requirementCodes.length > 0 ? (
        <section aria-label="Remaining setup">
          <h2>Still needed</h2>
          <ul>{requirementCodes.map((code) => <li key={code}>{REQUIREMENT_LABELS[code] ?? "Complete this setup item."}</li>)}</ul>
        </section>
      ) : null}
      <label>Business name<input disabled={!canEdit} value={values.business_name} onChange={(event) => update("business_name", event.target.value)} /></label>
      <label>Primary use case
        <select disabled={!canEdit} value={values.use_case} onChange={(event) => update("use_case", event.target.value)}>
          <option value="">Choose a use case</option>
          <option value="customer_support">Customer support</option>
          <option value="lead_qualification">Lead qualification</option>
          <option value="appointments">Appointments</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label>Languages<input disabled={!canEdit} value={values.languages.join(", ")} onChange={(event) => update("languages", event.target.value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean))} /></label>
      <label>Operating region<input disabled={!canEdit} value={values.operating_region} onChange={(event) => update("operating_region", event.target.value)} /></label>
      <label>Timezone<input disabled={!canEdit} value={values.timezone} onChange={(event) => update("timezone", event.target.value)} /></label>
      <label>Escalation email<input disabled={!canEdit} type="email" value={values.escalation_email ?? ""} onChange={(event) => update("escalation_email", event.target.value)} /></label>
      <button disabled={!canEdit || status === "saving"} type="submit">Save and continue</button>
      <p aria-live="polite">
        {status === "saving" ? "Saving onboarding…" : null}
        {status === "saved" ? "Onboarding saved." : null}
        {status === "error" ? message || "Onboarding could not be saved." : null}
      </p>
    </form>
  );
}
