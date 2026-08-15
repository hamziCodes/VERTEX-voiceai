'use client';

/**
 * TOP BAR — spec §3, verbatim:
 * "organization switcher (multi-org users), mode badge,
 *  notifications bell, user menu."
 *
 * Exactly those four. Nothing else lives here.
 *
 * A note on the demo controls: §2.1 says data mode is "set by Awaaz admins per
 * organization, never self-serve", and §2.2's roles arrive with the session. So the spec's
 * top bar has a mode *badge*, not a mode *switcher*. But the guide (Part F.3) requires both
 * to be togglable so every gated surface can be exercised. Both toggles therefore live
 * inside the user menu under an explicit "Demo controls" heading — visibly not a product
 * feature — while the badge itself stays in the top bar exactly as §3 specifies. The
 * interface-language switcher sits with them, for the same reason.
 */

import React, { useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useClerk } from '@clerk/nextjs';
import { Bell, Building2, Check, ChevronDown, CircleUser, LogOut, Clock } from 'lucide-react';

import { cn } from '@/lib/utils';
import { useLocale } from '@/i18n/locale-context';
import { LOCALE_LABELS, SUPPORTED_LOCALES, type Locale } from '@/i18n/config';
import { DEMO_CONTROLS_ENABLED, useSession } from '@/shared/session-context';
import type { LiveNotificationCounts } from '@/lib/dashboard-live';
import { formatCount, formatLiveClock, displayTimezone } from '@/lib/format';
import { ALL_ORGS } from '@/mock/orgs';
import { DATA_MODE_LABELS, DATA_MODES, ROLE_LABELS, ROLES } from '@/shared/status-models';
import type { DataMode, Role } from '@/shared/status-models';

const menuContentClass =
  'z-50 min-w-[14rem] max-w-[20rem] overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md';
const menuItemClass =
  'relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground';
const triggerClass =
  'inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-sm hover:bg-accent';

/** §3 "organization switcher (multi-org users)" — hidden when the user has only one org. */
function OrganizationSwitcher(): React.JSX.Element | null {
  const { org, setOrgId } = useSession();
  const { t } = useLocale();
  if (ALL_ORGS.length < 2) return null;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className={triggerClass} aria-label={`${t('topbar.organization')}: ${org.name}. ${t('topbar.changeOrganization')}`}>
        <Building2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="max-w-[16ch] truncate font-medium">{org.name}</span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={menuContentClass} align="start" sideOffset={6}>
          <DropdownMenu.Label className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t('topbar.organization')}
          </DropdownMenu.Label>
          {ALL_ORGS.map((o) => (
            <DropdownMenu.Item key={o.id} className={menuItemClass} onSelect={() => setOrgId(o.id)}>
              <Check className={cn('h-4 w-4', o.id === org.id ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
              <span>{o.name}</span>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/**
 * §2.1 "Every page header renders a mode badge: NON-PHI or PHI-BAA."
 * Read-only by design — the switcher is a demo control in the user menu.
 */
function ModeBadge(): React.JSX.Element {
  const { session } = useSession();
  const { t } = useLocale();
  const isPhi = session.mode === 'PHI_BAA';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold',
        isPhi ? 'border-border bg-muted text-foreground' : 'border-border bg-card text-muted-foreground',
      )}
      title={isPhi ? t('topbar.modePhiTitle') : t('topbar.modeNonPhiTitle')}
    >
      {DATA_MODE_LABELS[session.mode]}
    </span>
  );
}

/** §3 notifications bell — total count with breakdown on hover / click. */
function NotificationsBell({ counts }: { counts: LiveNotificationCounts | null }): React.JSX.Element {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const total = counts?.total ?? 0;
  const escalations = counts?.escalationsPending ?? 0;
  const vobPending = counts?.vobPendingCalls ?? 0;

  const label =
    total > 0 ? `${t('topbar.notifications')}: ${total} ${t('topbar.unread')}` : t('topbar.notificationsNone');

  const clearCloseTimer = () => {
    if (closeTimer.current !== null) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimer.current = setTimeout(() => setOpen(false), 160);
  };

  useEffect(() => () => clearCloseTimer(), []);

  const badgeLabel = total > 99 ? '99+' : String(total);

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen} modal={false}>
      <DropdownMenu.Trigger
        className={cn(triggerClass, 'relative px-2')}
        aria-label={label}
        title={label}
        onPointerEnter={() => {
          clearCloseTimer();
          setOpen(true);
        }}
        onPointerLeave={scheduleClose}
      >
        <Bell className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        {total > 0 ? (
          <span
            className="absolute -right-1 -top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground"
            aria-hidden="true"
          >
            {badgeLabel}
          </span>
        ) : null}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={cn(menuContentClass, 'min-w-[18rem]')}
          align="end"
          sideOffset={6}
          onPointerEnter={clearCloseTimer}
          onPointerLeave={scheduleClose}
        >
          <DropdownMenu.Label className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t('topbar.notifications')}
          </DropdownMenu.Label>
          <DropdownMenu.Item className={menuItemClass} asChild>
            <Link href="/escalations?status=pending">
              <span className="flex flex-1 items-center justify-between gap-3">
                <span>{t('topbar.notificationsEscalations')}</span>
                <span className="font-semibold tabular-nums">{formatCount(escalations)}</span>
              </span>
            </Link>
          </DropdownMenu.Item>
          <DropdownMenu.Item className={menuItemClass} asChild>
            <Link href="/vob-queue">
              <span className="flex flex-1 items-center justify-between gap-3">
                <span>{t('topbar.notificationsVobCalls')}</span>
                <span className="font-semibold tabular-nums">{formatCount(vobPending)}</span>
              </span>
            </Link>
          </DropdownMenu.Item>
          {total === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">{t('topbar.notificationsNone')}</p>
          ) : null}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/**
 * §3 "user menu": the signed-in identity, sign-out, the §2.7 locale switcher, and — in
 * development builds only — the guide's F.3 demo controls for role and mode.
 *
 * The demo controls are behind `DEMO_CONTROLS_ENABLED`, which resolves to `false` at build
 * time in production. The markup is removed by dead-code elimination, not hidden: a
 * deployed build offers no way to change your own role.
 */
function UserMenu(): React.JSX.Element {
  const { session, authenticatedRole, setRole, setMode } = useSession();
  const { t, locale, setLocale } = useLocale();
  const { signOut } = useClerk();
  const [open, setOpen] = useState(false);

  const overridden = DEMO_CONTROLS_ENABLED && session.role !== authenticatedRole;

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger
        className={cn(triggerClass, 'px-2')}
        aria-label={`${t('topbar.userMenu')}. ${t('topbar.signedInAs')} ${session.actor}, ${ROLE_LABELS[session.role]}`}
      >
        <CircleUser className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={cn(menuContentClass, 'max-h-[80vh] overflow-y-auto')} align="end" sideOffset={6}>
          <div className="px-2 py-2">
            <p className="truncate text-sm font-medium">{session.actor}</p>
            <p className="text-xs text-muted-foreground">
              {ROLE_LABELS[session.role]}
              {overridden ? ` (overridden; granted ${ROLE_LABELS[authenticatedRole]})` : null}
            </p>
          </div>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item className={menuItemClass} onSelect={() => void signOut({ redirectUrl: '/sign-in' })}>
            <LogOut className="h-4 w-4" aria-hidden="true" />
            <span>{t('topbar.signOut')}</span>
          </DropdownMenu.Item>

          {/* §2.7: the i18n framework, exposed so it is demonstrably working rather than dead code. */}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Label className="px-2 text-xs font-medium text-muted-foreground">
            {t('topbar.interfaceLanguage')}
          </DropdownMenu.Label>
          <p className="px-2 pb-1.5 text-xs leading-snug text-muted-foreground">{t('topbar.interfaceLanguageNote')}</p>
          {SUPPORTED_LOCALES.map((l: Locale) => (
            <DropdownMenu.Item key={l} className={menuItemClass} onSelect={() => setLocale(l)}>
              <Check className={cn('h-4 w-4', locale === l ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
              <span>{LOCALE_LABELS[l]}</span>
            </DropdownMenu.Item>
          ))}

          {DEMO_CONTROLS_ENABLED ? (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Label className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('topbar.demoControls')}
              </DropdownMenu.Label>
              <p className="px-2 text-xs font-medium leading-snug text-destructive">{t('topbar.devOnly')}</p>
              <p className="px-2 pb-1.5 pt-1 text-xs leading-snug text-muted-foreground">{t('topbar.demoControlsNote')}</p>

              <DropdownMenu.Label className="px-2 pt-1 text-xs font-medium text-muted-foreground">
                {t('topbar.role')}
              </DropdownMenu.Label>
              {ROLES.map((r: Role) => (
                <DropdownMenu.Item key={r} className={menuItemClass} onSelect={() => setRole(r)}>
                  <Check className={cn('h-4 w-4', session.role === r ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
                  <span>{ROLE_LABELS[r]}</span>
                </DropdownMenu.Item>
              ))}

              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Label className="px-2 text-xs font-medium text-muted-foreground">
                {t('topbar.dataMode')}
              </DropdownMenu.Label>
              {DATA_MODES.map((m: DataMode) => (
                <DropdownMenu.Item key={m} className={menuItemClass} onSelect={() => setMode(m)}>
                  <Check className={cn('h-4 w-4', session.mode === m ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
                  <span>{DATA_MODE_LABELS[m]}</span>
                </DropdownMenu.Item>
              ))}
            </>
          ) : null}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
function SessionClock(): React.JSX.Element | null {
  const { session, org } = useSession();
  const timeZone = displayTimezone(session, org);
  const [mounted, setMounted] = useState(false);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(() => {
      setTime(new Date());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted) return null;

  const timeString = formatLiveClock(time, timeZone);

  return (
    <div
      className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-sm text-muted-foreground"
      title={timeZone.replace(/_/g, ' ')}
    >
      <Clock className="h-4 w-4" aria-hidden="true" />
      <span className="font-medium">{timeString}</span>
    </div>
  );
}


export function TopBar({ notifications }: { notifications: LiveNotificationCounts | null }): React.JSX.Element {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/95 px-4 backdrop-blur">
      <div className="flex items-center gap-2">
        <OrganizationSwitcher />
      </div>
      <div className="flex items-center gap-2">
        <SessionClock />
        <ModeBadge />
        <NotificationsBell counts={notifications} />
        <UserMenu />
      </div>
    </header>
  );
}
