export async function sendAlert(
  title: string,
  details: Record<string, unknown> = {},
): Promise<void> {
  const payload = {
    title,
    details,
    sent_at: new Date().toISOString(),
  };

  const webhookUrl = Deno.env.get("ALERT_WEBHOOK_URL") ?? "";
  if (!webhookUrl) {
    console.warn("alert webhook not configured", JSON.stringify(payload));
    return;
  }

  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      console.error("alert webhook failed", response.status, await response.text());
    }
  } catch (error) {
    console.error("alert webhook error", error instanceof Error ? error.message : String(error));
  }
}
