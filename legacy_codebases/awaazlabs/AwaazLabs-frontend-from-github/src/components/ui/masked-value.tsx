'use client';

import React, { useState } from 'react';
import { Eye } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PermissionDeniedError,
  revealPhone,
  type PatientIdentityView,
  type Session,
} from '@/mock/data-access';

/**
 * SECURITY-CRITICAL. §5.2 "Phone (masked as pattern, click-to-reveal, reveal audited)".
 *
 * The reveal control appears ONLY when `identity.phoneE164 !== null`. For a Viewer the
 * raw value never crosses the data boundary (the data-access layer omits it), so there is
 * nothing to reveal and no button is rendered — this is structural, not a CSS mask and not
 * a role check performed here. The audit event is written by `revealPhone`, not here.
 */
export function MaskedValue({
  identity,
  session,
  objectRef,
  className,
}: {
  identity: PatientIdentityView;
  session: Session;
  objectRef: string;
  className?: string;
}) {
  const [revealedValue, setRevealedValue] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canReveal = identity.phoneE164 !== null;

  const handleReveal = () => {
    try {
      const raw = revealPhone(identity, session, objectRef);
      setRevealedValue(raw);
      setError(null);
    } catch (e) {
      // Never surface the underlying message (it names role/mode); keep it non-leaking.
      setError(e instanceof PermissionDeniedError ? 'Reveal not permitted.' : 'Unable to reveal.');
    }
  };

  if (revealedValue !== null) {
    return <span className={cn('tabular-nums', className)}>{revealedValue}</span>;
  }

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className="tabular-nums">{identity.phoneMasked}</span>
      {canReveal ? (
        <button
          type="button"
          onClick={handleReveal}
          aria-label={`Reveal phone number for ${identity.firstName} ${identity.lastName}`}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        >
          <Eye className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : null}
      {error ? (
        <span role="status" className="text-xs text-muted-foreground">
          {error}
        </span>
      ) : null}
    </span>
  );
}
