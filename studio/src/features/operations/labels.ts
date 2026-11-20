/** Turn a server enum such as `consent_blocked` into readable text without inventing meaning. */
export function humanize(value: string): string {
  const spaced = value.replaceAll("_", " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : "Unknown";
}

export function transportLabel(value: string): string {
  if (value === "sip") return "SIP";
  if (value === "websocket") return "Web";
  return value;
}

export function dispositionTone(value: string): "success" | "danger" | "warning" | "neutral" {
  if (value === "completed") return "success";
  if (value === "failed" || value === "error") return "danger";
  if (value === "in_progress" || value === "active") return "warning";
  return "neutral";
}
