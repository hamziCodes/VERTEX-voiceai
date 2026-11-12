// Fixed locale and UTC so server-rendered and hydrated text always match.
const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const NUMBER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateTime(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const parsed = parse(value);
  return parsed ? `${DATE_TIME.format(parsed)} UTC` : "Unknown time";
}

export function formatDate(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const parsed = parse(value);
  return parsed ? DATE.format(parsed) : "Unknown date";
}

export function formatNumber(value: number): string {
  return NUMBER.format(value);
}
