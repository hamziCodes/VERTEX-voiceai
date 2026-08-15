/**
 * NAVIGATION TREE — spec §3, built exactly. Nothing more, nothing less.
 *
 * FROZEN FILE (Foundation).
 *
 * Guide Part F.2: "build exactly this tree, nothing more, nothing less."
 * Guide Part H step 3: Phase 3 re-runs the nav diff; "zero unlisted extras may exist
 * anywhere (routes, nav items, stat cards, columns, buttons)."
 *
 * Labels are `MessageKey`s, not strings — §2.7 requires the i18n framework, and the nav is
 * the chrome it translates. The English text lives in `src/i18n/messages/en.ts`.
 *
 * Every entry carries the spec subsection it implements, so an auditor can trace each nav
 * item to a spec line and delete anything that cannot be traced.
 */

import type { MessageKey } from '@/i18n/messages/en';
import type { Session } from '@/mock/data-access';
import { canSeeAuditLog, canSeeBilling, canSeeMembers } from '@/mock/data-access';

export interface NavItem {
  readonly labelKey: MessageKey;
  readonly href: string;
  /** lucide-react icon name, resolved through an allow-list in the shell. */
  readonly icon: string;
  /** The spec subsection this surface implements. Used by the Phase 3 coverage audit. */
  readonly specRef: string;
  readonly subItems?: readonly NavItem[];
  /** Gate. Absent means "visible to everyone in every mode". */
  readonly visibleWhen?: (session: Session) => boolean;
}

export interface NavGroup {
  readonly titleKey: MessageKey;
  readonly items: readonly NavItem[];
  readonly visibleWhen?: (session: Session) => boolean;
}

/**
 * §3, in the spec's exact order. "The demo narrative walks top to bottom in exactly this
 * order" — so the order here is a product decision, not a style choice. Do not sort it.
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    titleKey: 'nav.group.home',
    items: [{ labelKey: 'nav.overview', href: '/', icon: 'LayoutDashboard', specRef: '§4' }],
  },
  {
    titleKey: 'nav.group.operations',
    items: [
      { labelKey: 'nav.appointments', href: '/appointments', icon: 'CalendarDays', specRef: '§5' },
      {
        labelKey: 'nav.conversations',
        href: '/conversations/calls',
        icon: 'MessagesSquare',
        specRef: '§10',
        subItems: [
          { labelKey: 'nav.calls', href: '/conversations/calls', icon: 'PhoneCall', specRef: '§10.1' },
          { labelKey: 'nav.chats', href: '/conversations/chats', icon: 'MessageSquare', specRef: '§10.2' },
        ],
      },
      { labelKey: 'nav.escalations', href: '/escalations', icon: 'TriangleAlert', specRef: '§11' },
      { labelKey: 'nav.vobQueue', href: '/vob-queue', icon: 'ClipboardCheck', specRef: '§8' },
    ],
  },
  {
    titleKey: 'nav.group.agents',
    items: [
      { labelKey: 'nav.receptionist', href: '/agents/receptionist', icon: 'Headset', specRef: '§6' },
      { labelKey: 'nav.vobAgent', href: '/agents/vob', icon: 'ShieldCheck', specRef: '§7' },
      { labelKey: 'nav.chatAgents', href: '/agents/chat', icon: 'Bot', specRef: '§9' },
      { labelKey: 'nav.reviewTaker', href: '/agents/review-taker', icon: 'Star', specRef: '§13.1' },
      { labelKey: 'nav.reengagement', href: '/agents/reengagement', icon: 'PhoneOutgoing', specRef: '§14.1' },
      // §3: "(custom agents append here from the registry)". The shell appends entries
      // from the agent registry (§2.6) at this position, rendering /agents/[slug].
    ],
  },
  {
    titleKey: 'nav.group.quality',
    items: [
      { labelKey: 'nav.quality', href: '/quality', icon: 'Sparkles', specRef: '§12' },
      { labelKey: 'nav.knowledge', href: '/knowledge', icon: 'BookOpen', specRef: '§15' },
    ],
  },
  {
    titleKey: 'nav.group.growth',
    items: [
      { labelKey: 'nav.reviews', href: '/reviews', icon: 'ThumbsUp', specRef: '§13.2' },
      { labelKey: 'nav.campaigns', href: '/campaigns', icon: 'Megaphone', specRef: '§14.2' },
    ],
  },
  {
    titleKey: 'nav.group.insights',
    items: [{ labelKey: 'nav.reports', href: '/reports', icon: 'FileDown', specRef: '§16.1' }],
  },
  {
    // §3: "COMPLIANCE (PHI mode only)". §16.2 narrows further: "PHI mode only, Owner only".
    titleKey: 'nav.group.compliance',
    visibleWhen: canSeeAuditLog,
    items: [{ labelKey: 'nav.auditLog', href: '/audit-log', icon: 'ScrollText', specRef: '§16.2' }],
  },
  {
    titleKey: 'nav.group.settings',
    items: [
      { labelKey: 'nav.members', href: '/settings/members', icon: 'Users', specRef: '§16.3', visibleWhen: canSeeMembers },
      { labelKey: 'nav.billing', href: '/settings/billing', icon: 'Receipt', specRef: '§16.4', visibleWhen: canSeeBilling },
      { labelKey: 'nav.organization', href: '/settings/organization', icon: 'Building2', specRef: '§16.5' },
      { labelKey: 'nav.lines', href: '/settings/lines', icon: 'Hash', specRef: '§16.5' },
      { labelKey: 'nav.consent', href: '/settings/consent', icon: 'PhoneOff', specRef: '§16.5' },
      { labelKey: 'nav.notifications', href: '/settings/notifications', icon: 'Bell', specRef: '§16.6' },
    ],
  },
];

/** Apply role/mode gating. A hidden group with no visible items disappears entirely. */
export function visibleNavGroups(session: Session): readonly NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.visibleWhen?.(session) ?? true),
  })).filter((group) => (group.visibleWhen?.(session) ?? true) && group.items.length > 0);
}

/** Flat list of every route the nav can reach, for the Phase 3 coverage audit. */
export function allNavRoutes(): readonly { href: string; specRef: string }[] {
  return NAV_GROUPS.flatMap((g) =>
    g.items.flatMap((i) => [
      { href: i.href, specRef: i.specRef },
      ...(i.subItems ?? []).map((s) => ({ href: s.href, specRef: s.specRef })),
    ]),
  );
}

export function isRouteActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(`${href}/`);
}
