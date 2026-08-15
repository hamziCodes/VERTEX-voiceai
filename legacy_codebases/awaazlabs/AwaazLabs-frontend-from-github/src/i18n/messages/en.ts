/**
 * English message catalogue — the source of truth for message keys (spec §2.7).
 *
 * `MessageKey` is derived from this object, and `es.ts` is typed as
 * `Record<MessageKey, string>`. Adding a key here without translating it in `es.ts` is a
 * **compile error**, not a runtime fallback to English. That is what makes this a framework
 * rather than a wishful `t()` helper.
 *
 * Scope note (§2.7, literally): "UI ships English." The application *chrome* — navigation,
 * top bar, shared empty/placeholder states — is translated. Page bodies remain English by
 * design, because the spec ships English and names Spanish only as the second *target*.
 * Extending coverage is adding keys here and there; nothing structural changes.
 */

export const en = {
  // --- Navigation groups (§3, in the spec's order) ---
  'nav.group.home': 'HOME',
  'nav.group.operations': 'OPERATIONS',
  'nav.group.agents': 'AGENTS',
  'nav.group.quality': 'QUALITY',
  'nav.group.growth': 'GROWTH',
  'nav.group.insights': 'INSIGHTS',
  'nav.group.compliance': 'COMPLIANCE',
  'nav.group.settings': 'SETTINGS',

  // --- Navigation items (§3) ---
  'nav.overview': 'Overview',
  'nav.appointments': 'Appointments',
  'nav.conversations': 'Conversations',
  'nav.calls': 'Calls',
  'nav.chats': 'Chats',
  'nav.escalations': 'Escalations',
  'nav.vobQueue': 'VOB Queue',
  'nav.receptionist': 'Receptionist',
  'nav.vobAgent': 'VOB Agent',
  'nav.chatAgents': 'Chat Agents',
  'nav.reviewTaker': 'Review Taker',
  'nav.reengagement': 'Reengagement',
  'nav.quality': 'Quality and Optimization',
  'nav.knowledge': 'Agent Knowledge',
  'nav.reviews': 'Reviews',
  'nav.campaigns': 'Campaigns',
  'nav.reports': 'Reports and Exports',
  'nav.auditLog': 'Audit Log',
  'nav.members': 'Members',
  'nav.billing': 'Usage and Billing',
  'nav.organization': 'Organization and Locations',
  'nav.lines': 'Lines and Numbers',
  'nav.consent': 'Consent and Do-Not-Call',
  'nav.notifications': 'Notifications',

  // --- Shell chrome ---
  'shell.skipToContent': 'Skip to main content',
  'shell.mainNavigation': 'Main navigation',
  'shell.expandNavigation': 'Expand navigation',
  'shell.collapseNavigation': 'Collapse navigation',

  // --- Top bar (§3) ---
  'topbar.organization': 'Organization',
  'topbar.changeOrganization': 'Change organization',
  'topbar.allLocations': 'All locations',
  'topbar.changeLocation': 'Change location',
  'topbar.locationFilter': 'Location filter',
  'topbar.notifications': 'Notifications',
  'topbar.unread': 'unread',
  'topbar.notificationsNone': 'Notifications: none unread',
  'topbar.notificationsEscalations': 'Escalations to acknowledge or resolve',
  'topbar.notificationsVobCalls': 'Pending insurance verification calls',
  'topbar.userMenu': 'User menu',
  'topbar.signOut': 'Sign out',
  'topbar.devOnly': 'Development build only — absent in production',
  'topbar.signedInAs': 'Signed in as',
  'topbar.demoControls': 'Demo controls',
  'topbar.demoControlsNote':
    'Not a product feature. In a real deployment role and mode arrive with the session; mode is set by Awaaz admins per organization and is never self-serve (§2.1).',
  'topbar.role': 'Role',
  'topbar.dataMode': 'Data mode',
  'topbar.interfaceLanguage': 'Interface language',
  'topbar.interfaceLanguageNote':
    'The i18n framework is in place per §2.7. Application chrome is translated; page bodies ship English, with Spanish as the second locale target.',
  'topbar.modePhiTitle': 'PHI-BAA mode: full patient-level detail. Requires an executed BAA.',
  'topbar.modeNonPhiTitle':
    'NON-PHI mode: aggregates and analytics only. No patient identity, recordings, or transcripts.',

  // --- Under construction placeholder ---
  'underConstruction.badge': 'Under construction',
  'underConstruction.spec': 'Spec:',
  'underConstruction.plannedFor': 'Planned for:',
  'underConstruction.milestone2': 'Milestone 2',

  // --- Route guard (§2.2) ---
  'guard.notAvailable': 'is not available',
  'guard.explanation':
    'Your role and the workspace’s current data mode do not grant access to this surface. If you believe this is wrong, contact your organization owner.',
} as const;

export type MessageKey = keyof typeof en;
export type Messages = Readonly<Record<MessageKey, string>>;
