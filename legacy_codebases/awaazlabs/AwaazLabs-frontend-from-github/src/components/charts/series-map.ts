/**
 * series-map.ts — the single place that binds a data ENTITY to a color.
 *
 * THEME_NOTES.md §3: "Color follows the entity, not its rank." Filtering a series out must
 * never repaint the survivors, so every binding here is a fixed lookup keyed by the entity,
 * assigned in slot order once and never cycled. Voice is always `--chart-1`, WhatsApp always
 * `--chart-2`, etc. — regardless of which series are visible.
 *
 * Every value is a CSS custom-property reference (`var(--chart-n)`) or a documented chrome
 * token (`hsl(var(--…))`). No literal color appears here. Status tokens
 * (`--destructive` / `--status-warning`) are used ONLY where the entity carries a genuine
 * good/bad meaning (THEME_NOTES §3, §5); categorical series never borrow them.
 *
 * All maps are `Readonly` at the type level and imported, never inlined.
 */

import {
  isVobNeedsAttention,
  type AppointmentSource,
  type ChatChannel,
  type TriageFlag,
  type VobStatus,
} from '@/shared/status-models';

/* ----------------------------------------------------------------------------------------
 * Appointment sources — §4.1 bookings-over-time, §5.2 source column
 * -------------------------------------------------------------------------------------- */

/**
 * Fixed slot order. §4.1's chart plots only Voice/WhatsApp/Web Chat, but Form is bound too
 * so the color follows the entity wherever a source appears.
 */
export const SOURCE_SERIES: Readonly<Record<AppointmentSource, string>> = {
  voice: 'var(--chart-1)',
  whatsapp: 'var(--chart-2)',
  web_chat: 'var(--chart-3)',
  form: 'var(--chart-4)',
};

/* ----------------------------------------------------------------------------------------
 * Chat channels — §9.1 / §9.2 sessions split by channel
 * -------------------------------------------------------------------------------------- */

/** Same hues as SOURCE_SERIES: WhatsApp and Web Chat keep their identity across tabs. */
export const CHAT_CHANNEL_SERIES: Readonly<Record<ChatChannel, string>> = {
  whatsapp: 'var(--chart-2)',
  web_chat: 'var(--chart-3)',
};

/* ----------------------------------------------------------------------------------------
 * Chat performance metrics — §9.2 grouped bars
 * -------------------------------------------------------------------------------------- */

/**
 * Four DISTINCT metrics compared side by side — a categorical comparison, not a good/bad
 * scale of one quantity — so they take categorical chart tokens in fixed spec order.
 * (Escalation to a human is a legitimate safety outcome, not a failure, so it is not painted
 * with a reserved status token.)
 */
export const CHAT_METRICS = ['containment', 'resolution', 'deflection', 'escalation'] as const;
export type ChatMetric = (typeof CHAT_METRICS)[number];

export const CHAT_METRIC_SERIES: Readonly<Record<ChatMetric, string>> = {
  containment: 'var(--chart-1)',
  resolution: 'var(--chart-2)',
  deflection: 'var(--chart-3)',
  escalation: 'var(--chart-4)',
};

/* ----------------------------------------------------------------------------------------
 * Attributed vs organic reviews — §13.2 stacked bars
 * -------------------------------------------------------------------------------------- */

/**
 * Attributed reviews are the agent's contribution (the story this dashboard tells), so they
 * take the primary hue; organic reviews recede into a neutral chrome tone. Neither "means
 * bad", so no status token is involved.
 */
export const REVIEW_ATTRIBUTION = ['attributed', 'organic'] as const;
export type ReviewAttribution = (typeof REVIEW_ATTRIBUTION)[number];

export const REVIEW_ATTRIBUTION_SERIES: Readonly<Record<ReviewAttribution, string>> = {
  attributed: 'var(--chart-1)',
  organic: 'hsl(var(--muted-foreground))',
};

/* ----------------------------------------------------------------------------------------
 * Triage flags — §5.2 / §6.2 (red accents on High and Urgent)
 * -------------------------------------------------------------------------------------- */

/**
 * Triage is an ordinal SEVERITY, not a categorical set — precisely the "means good/bad" case
 * (THEME_NOTES §3). None/Low are benign and recede into chrome neutrals; High escalates to
 * amber and Urgent to red, exactly matching the spec's "red accents on High and Urgent".
 * These status tokens carry a real status here, so §5's "reserved" rule is honored, not
 * broken.
 */
/**
 * NOTE ON TOKEN FORM: `--destructive` is stored as a bare HSL triple (`0 84.2% 60.2%`) like
 * every base UI token, so it must be wrapped: `hsl(var(--destructive))`. The chart and
 * status tokens (`--chart-*`, `--seq-*`, `--status-warning`) are stored as complete color
 * values and are used bare. Getting this wrong yields an invalid SVG `fill`, which silently
 * paints the mark **black** rather than erroring. See THEME_NOTES.md §1 vs §3.
 */
export const TRIAGE_SERIES: Readonly<Record<TriageFlag, string>> = {
  none: 'hsl(var(--border))',
  low: 'hsl(var(--muted-foreground))',
  high: 'var(--status-warning)',
  urgent: 'hsl(var(--destructive))',
};

/* ----------------------------------------------------------------------------------------
 * VOB status groups — §7.2 distribution, §4.2 compact distribution
 * -------------------------------------------------------------------------------------- */

/**
 * The eight terminal VOB statuses roll into three meaningful groups. `verified` is the
 * success outcome (green — the theme has no reserved success token, so a categorical green
 * impersonates nothing); pending covers queued + in-progress; needs_attention is the
 * red-accented exception group the spec routes to the worklist (§4.2, §7.3).
 */
export const VOB_STATUS_GROUPS = ['verified', 'pending', 'needs_attention'] as const;
export type VobStatusGroup = (typeof VOB_STATUS_GROUPS)[number];

export const VOB_STATUS_GROUP_SERIES: Readonly<Record<VobStatusGroup, string>> = {
  verified: 'var(--chart-4)',
  pending: 'var(--chart-1)',
  // `hsl(...)` wrapper is required — see the note on TRIAGE_SERIES above.
  needs_attention: 'hsl(var(--destructive))',
};

export const VOB_STATUS_GROUP_LABELS: Readonly<Record<VobStatusGroup, string>> = {
  verified: 'Verified',
  pending: 'In progress',
  needs_attention: 'Needs attention',
};

/** Classifies any VOB status into its display group, reusing the canonical predicates. */
export function vobStatusGroup(status: VobStatus): VobStatusGroup {
  if (status === 'verified') return 'verified';
  if (isVobNeedsAttention(status)) return 'needs_attention';
  return 'pending';
}
