'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { LiveTranscriptTurn } from './live-transcript';
import {
  clearPlaybackSession,
  readPlaybackSession,
  writePlaybackSession,
} from './transcript-playback-session';
import { TypewriterRedactedText } from './typewriter-redacted-text';
import { useTypewriterErase, useTypewriterText } from './use-typewriter-text';
import { buildTranscriptPlaybackState, hasPatientTurn, type TranscriptRound } from './transcript-rounds';

type PreviewPhase = 'typing' | 'hold' | 'erasing';

/** Pause on a finished round before erasing when another sealed round is queued. */
const HOLD_BEFORE_ERASE_MS = 900;
const HOLD_AFTER_TYPING_MS = 500;

function speakerLabel(speaker: LiveTranscriptTurn['speaker']): string {
  return speaker === 'agent' ? 'Agent' : 'Customer';
}

function PreviewPending({
  pending,
  waitingForSeal,
}: {
  pending: { agent?: LiveTranscriptTurn; patient?: LiveTranscriptTurn };
  waitingForSeal?: boolean;
}): React.JSX.Element | null {
  if (waitingForSeal) {
    return <p className="text-xs text-muted-foreground">Waiting for the exchange to finish…</p>;
  }
  if (!pending.agent) return null;
  return <p className="text-xs text-muted-foreground">Agent speaking…</p>;
}

function PreviewRoundTyping({
  round,
  roundKey,
  onFinished,
}: {
  round: TranscriptRound;
  roundKey: string;
  onFinished: () => void;
}): React.JSX.Element {
  const [phase, setPhase] = useState<'agent' | 'patient'>('agent');
  const agentVisible = useTypewriterText(round.agent.text, phase === 'agent', 42);
  const patientText = round.patient?.text ?? '';
  const patientVisible = useTypewriterText(patientText, phase === 'patient', 42);

  useEffect(() => {
    setPhase('agent');
  }, [roundKey]);

  useEffect(() => {
    if (phase !== 'agent') return;
    if (!round.agent.text) {
      if (hasPatientTurn(round)) setPhase('patient');
      else onFinished();
      return;
    }
    if (agentVisible.length < round.agent.text.length) return;
    const timer = window.setTimeout(() => {
      if (hasPatientTurn(round)) setPhase('patient');
      else onFinished();
    }, 240);
    return () => window.clearTimeout(timer);
  }, [phase, agentVisible, round, onFinished]);

  useEffect(() => {
    if (phase !== 'patient') return;
    if (!patientText) {
      onFinished();
      return;
    }
    if (patientVisible.length < patientText.length) return;
    const timer = window.setTimeout(onFinished, HOLD_AFTER_TYPING_MS);
    return () => window.clearTimeout(timer);
  }, [phase, patientVisible, patientText, onFinished]);

  return (
    <div className="flex min-h-[3.5rem] flex-col gap-2 text-sm leading-6 text-foreground">
      <div>
        <span className="font-semibold text-muted-foreground">{speakerLabel('agent')}:</span>{' '}
        <TypewriterRedactedText
          text={phase === 'agent' ? agentVisible : round.agent.text}
          redactions={round.agent.redactions}
          active={phase === 'agent'}
        />
      </div>
      {phase === 'patient' && round.patient ? (
        <div>
          <span className="font-semibold text-muted-foreground">{speakerLabel('patient')}:</span>{' '}
          <TypewriterRedactedText text={patientVisible} redactions={round.patient.redactions} active />
        </div>
      ) : null}
    </div>
  );
}

function PreviewRoundHold({ round }: { round: TranscriptRound }): React.JSX.Element {
  return (
    <div className="flex min-h-[3.5rem] flex-col gap-2 text-sm leading-6 text-foreground">
      <div>
        <span className="font-semibold text-muted-foreground">{speakerLabel('agent')}:</span>{' '}
        <TypewriterRedactedText text={round.agent.text} redactions={round.agent.redactions} />
      </div>
      {hasPatientTurn(round) ? (
        <div>
          <span className="font-semibold text-muted-foreground">{speakerLabel('patient')}:</span>{' '}
          <TypewriterRedactedText
            text={round.patient!.text}
            redactions={round.patient!.redactions}
            showCursor
          />
        </div>
      ) : null}
    </div>
  );
}

function PreviewRoundErasing({
  round,
  roundKey,
  onFinished,
}: {
  round: TranscriptRound;
  roundKey: string;
  onFinished: () => void;
}): React.JSX.Element {
  const patientText = round.patient?.text ?? '';
  const [phase, setPhase] = useState<'patient' | 'agent'>(patientText ? 'patient' : 'agent');
  const patientErased = useTypewriterErase(patientText, phase === 'patient', 90);
  const agentErased = useTypewriterErase(round.agent.text, phase === 'agent', 90);

  useEffect(() => {
    setPhase(patientText ? 'patient' : 'agent');
  }, [roundKey, patientText]);

  useEffect(() => {
    if (phase !== 'patient') return;
    if (!patientText) {
      setPhase('agent');
      return;
    }
    if (patientErased.length > 0) return;
    const timer = window.setTimeout(() => setPhase('agent'), 160);
    return () => window.clearTimeout(timer);
  }, [phase, patientErased, patientText]);

  useEffect(() => {
    if (phase !== 'agent') return;
    if (!round.agent.text) {
      onFinished();
      return;
    }
    if (agentErased.length > 0) return;
    const timer = window.setTimeout(onFinished, 180);
    return () => window.clearTimeout(timer);
  }, [phase, agentErased, round.agent.text, onFinished]);

  return (
    <div className="flex min-h-[3.5rem] flex-col gap-2 text-sm leading-6 text-foreground">
      {round.agent.text ? (
        <div>
          <span className="font-semibold text-muted-foreground">{speakerLabel('agent')}:</span>{' '}
          <TypewriterRedactedText
            text={phase === 'agent' ? agentErased : round.agent.text}
            redactions={round.agent.redactions}
            erasing={phase === 'agent'}
          />
        </div>
      ) : null}
      {phase === 'patient' && patientText ? (
        <div>
          <span className="font-semibold text-muted-foreground">{speakerLabel('patient')}:</span>{' '}
          <TypewriterRedactedText text={patientErased} redactions={round.patient?.redactions ?? []} erasing />
        </div>
      ) : null}
    </div>
  );
}

/**
 * Overview live-calls preview: one sealed round at a time.
 * A round enters the queue only after both sides have finished and text is frozen.
 * Each round plays through fully (type → hold → erase) before the next begins.
 */
export function LiveTranscriptPreview({
  turns,
  callId,
  finalizePending = false,
  onDrainComplete,
}: {
  turns: readonly LiveTranscriptTurn[];
  callId: string;
  /** Seal any remaining rounds (call ended) and play through the full queue. */
  finalizePending?: boolean;
  /** Fired once every sealed round has been animated after finalize. */
  onDrainComplete?: () => void;
}): React.JSX.Element {
  const { sealedRounds, pending, liveCompleteCount } = useMemo(
    () => buildTranscriptPlaybackState(turns, finalizePending),
    [turns, finalizePending],
  );
  const sealedCount = sealedRounds.length;

  const saved = readPlaybackSession(callId);
  const [playbackIndex, setPlaybackIndex] = useState(saved.playbackIndex);
  const [phase, setPhase] = useState<PreviewPhase>(saved.phase);
  const furthestCompletedRef = useRef(saved.furthestCompletedIndex);
  const wasFinalizePendingRef = useRef(false);

  const persistSession = useCallback(
    (index: number, nextPhase: PreviewPhase) => {
      writePlaybackSession(callId, {
        playbackIndex: index,
        phase: nextPhase,
        furthestCompletedIndex: furthestCompletedRef.current,
      });
    },
    [callId],
  );

  useEffect(() => {
    const session = readPlaybackSession(callId);
    setPlaybackIndex(session.playbackIndex);
    setPhase(session.phase);
    furthestCompletedRef.current = session.furthestCompletedIndex;
    wasFinalizePendingRef.current = false;
  }, [callId]);

  // Call ended: skip rounds already shown live — only play what remains.
  useEffect(() => {
    if (!finalizePending) {
      wasFinalizePendingRef.current = false;
      return;
    }
    if (wasFinalizePendingRef.current) return;
    wasFinalizePendingRef.current = true;

    const resumeIndex = Math.min(furthestCompletedRef.current + 1, Math.max(0, sealedCount - 1));
    if (sealedCount === 0) return;

    if (resumeIndex >= sealedCount) {
      setPlaybackIndex(sealedCount - 1);
      setPhase('hold');
      persistSession(sealedCount - 1, 'hold');
      return;
    }

    setPlaybackIndex(resumeIndex);
    setPhase('typing');
    persistSession(resumeIndex, 'typing');
  }, [finalizePending, sealedCount, persistSession]);

  useEffect(() => {
    if (sealedCount > 0 && playbackIndex >= sealedCount) {
      const clamped = sealedCount - 1;
      setPlaybackIndex(clamped);
      setPhase('hold');
      persistSession(clamped, 'hold');
    }
  }, [playbackIndex, sealedCount, persistSession]);

  const displayIndex = sealedCount > 0 ? Math.min(playbackIndex, sealedCount - 1) : -1;
  const currentRound = displayIndex >= 0 ? sealedRounds[displayIndex] ?? null : null;
  const hasQueuedRound = playbackIndex < sealedCount - 1;
  const currentRoundKey = String(displayIndex);

  useEffect(() => {
    if (phase === 'hold' || phase === 'erasing') {
      furthestCompletedRef.current = Math.max(furthestCompletedRef.current, displayIndex);
      persistSession(playbackIndex, phase);
    }
  }, [phase, displayIndex, playbackIndex, persistSession]);

  // Live: hold → erase → next. Drain: hold → next (no erase).
  useEffect(() => {
    if (phase !== 'hold' || !hasQueuedRound) return;

    if (finalizePending) {
      const timer = window.setTimeout(() => {
        const next = playbackIndex + 1;
        setPlaybackIndex(next);
        setPhase('typing');
        persistSession(next, 'typing');
      }, 400);
      return () => window.clearTimeout(timer);
    }

    const timer = window.setTimeout(() => {
      setPhase('erasing');
      persistSession(playbackIndex, 'erasing');
    }, HOLD_BEFORE_ERASE_MS);
    return () => window.clearTimeout(timer);
  }, [phase, hasQueuedRound, finalizePending, playbackIndex, persistSession]);

  const isFullyDrained =
    finalizePending &&
    sealedCount > 0 &&
    playbackIndex >= sealedCount - 1 &&
    phase === 'hold' &&
    !hasQueuedRound &&
    furthestCompletedRef.current >= sealedCount - 1;

  useEffect(() => {
    if (!isFullyDrained || !onDrainComplete) return;
    const timer = window.setTimeout(() => {
      clearPlaybackSession(callId);
      onDrainComplete();
    }, 600);
    return () => window.clearTimeout(timer);
  }, [isFullyDrained, onDrainComplete, callId]);

  useEffect(() => {
    if (!finalizePending || !onDrainComplete) return;
    if (sealedCount === 0 && turns.length > 0 && pending.agent) return;
    if (sealedCount === 0 && turns.length === 0) {
      clearPlaybackSession(callId);
      onDrainComplete();
    }
  }, [finalizePending, sealedCount, turns.length, pending.agent, onDrainComplete, callId]);

  if (turns.length === 0) {
    return <p className="text-sm text-muted-foreground">Waiting for the first transcript turns.</p>;
  }

  if (!currentRound) {
    return <PreviewPending pending={pending} waitingForSeal={liveCompleteCount > 0 && sealedCount === 0} />;
  }

  return (
    <div className="flex flex-col gap-2">
      {phase === 'typing' ? (
        <PreviewRoundTyping
          round={currentRound}
          roundKey={currentRoundKey}
          onFinished={() => {
            furthestCompletedRef.current = Math.max(furthestCompletedRef.current, playbackIndex);
            setPhase('hold');
            persistSession(playbackIndex, 'hold');
          }}
        />
      ) : null}
      {phase === 'hold' ? <PreviewRoundHold round={currentRound} /> : null}
      {phase === 'erasing' && !finalizePending ? (
        <PreviewRoundErasing
          round={currentRound}
          roundKey={currentRoundKey}
          onFinished={() => {
            const next = playbackIndex + 1;
            setPlaybackIndex(next);
            setPhase('typing');
            persistSession(next, 'typing');
          }}
        />
      ) : null}
      {finalizePending ? (
        <p className="text-xs text-muted-foreground">Call ended — finishing transcript…</p>
      ) : (
        <PreviewPending pending={pending} />
      )}
    </div>
  );
}
