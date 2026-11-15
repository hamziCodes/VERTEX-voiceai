import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Check, Mic, RotateCcw } from 'lucide-react';
import { Waveform, type WaveState } from '@/components/Waveform';
import { Btn } from '@/components/ui';

type Phase = 'idle' | 'listening' | 'thinking' | 'speaking' | 'interrupted' | 'done';

const REPLY =
'Hi! I can help you book an appointment, answer questions, or transfer you to a person. Try cutting me off mid-sent—';

const WAVE: Record<Phase, WaveState> = {
  idle: 'idle',
  listening: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  interrupted: 'idle',
  done: 'idle'
};

const STATUS: Record<Phase, string> = {
  idle: 'Click the button and try interrupting me mid-sentence',
  listening: 'Listening — it picks up your voice as you speak',
  thinking: 'Thinking — working out what to say back',
  speaking: 'Speaking — go ahead, cut it off',
  interrupted: '',
  done: 'It finished on its own that time. Try again and interrupt it.'
};

export function InteractiveDemo() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [typed, setTyped] = useState(0);

  useEffect(() => {
    if (phase === 'listening') {
      const t = window.setTimeout(() => setPhase('thinking'), 2000);
      return () => window.clearTimeout(t);
    }

    if (phase === 'thinking') {
      const t = window.setTimeout(() => setPhase('speaking'), 800);
      return () => window.clearTimeout(t);
    }

    if (phase === 'speaking') {
      let i = 0;
      setTyped(0);
      const id = window.setInterval(() => {
        i += 1;
        setTyped(i);
        if (i >= REPLY.length) {
          window.clearInterval(id);
          setPhase('done');
        }
      }, 30);
      return () => window.clearInterval(id);
    }

    return undefined;
  }, [phase]);

  const start = () => {
    setTyped(0);
    setPhase('listening');
  };

  const interrupt = () => setPhase('interrupted');

  const reset = () => {
    setTyped(0);
    setPhase('idle');
  };

  const busy = phase === 'listening' || phase === 'thinking' || phase === 'speaking';
  const showBubble = phase === 'speaking' || phase === 'interrupted' || phase === 'done';
  const buttonLabel =
  phase === 'listening' ?
  'Listening...' :
  phase === 'thinking' ?
  'Thinking...' :
  phase === 'speaking' ?
  'Speaking...' :
  'Tap to talk';

  return (
    <motion.div data-ev-id="ev_a3d9e4e376"
    className="mx-auto w-full max-w-[600px] rounded-xl p-8 lg:p-10"
    style={{
      background: 'var(--theme-surface)',
      border: '1px solid var(--theme-border)'
    }}
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.6, ease: 'easeOut' }}>

			<div data-ev-id="ev_de90eca87b" className="flex flex-col items-center gap-8">
				<p data-ev-id="ev_dfdf0703d0" className="text-sm font-medium" style={{ color: 'var(--theme-fg-muted)' }}>
					Try it right now — no sign-up needed
				</p>

				<div data-ev-id="ev_3a012d1876"
        className="flex items-center justify-center rounded-xl p-6 border border-[var(--theme-border)]"
        style={{
          background: 'var(--theme-surface-2)',
        }}>

					<Waveform state={WAVE[phase]} height={80} barWidth={6} gap={6} />
				</div>

				<div data-ev-id="ev_53cbece8a6" className="flex w-full flex-col items-center gap-4 sm:flex-row sm:justify-center">
					<Btn onClick={start} disabled={busy} className="w-full px-8 sm:w-auto">
						<Mic size={18} aria-hidden="true" />
						{buttonLabel}
					</Btn>

					<AnimatePresence>
						{phase === 'speaking' &&
            <motion.div data-ev-id="ev_ecd435cfa7"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.25 }}
            className="w-full sm:w-auto">

								<Btn variant="outline" onClick={interrupt} className="w-full px-8 sm:w-auto">
									Interrupt it
								</Btn>
							</motion.div>
            }
					</AnimatePresence>
				</div>

				<div data-ev-id="ev_f4d1c3a97d" aria-live="polite" className="min-h-6 text-center">
					{phase === 'interrupted' ?
          <p data-ev-id="ev_a6c7d7b806" className="flex items-center justify-center gap-2 text-sm font-medium" style={{ color: 'var(--theme-success)' }}>
							<Check size={16} aria-hidden="true" />
							Stopped instantly — just like a real person would.
						</p> :

          <p data-ev-id="ev_ffa3b70466" className="text-sm" style={{ color: 'var(--theme-fg-muted)' }}>{STATUS[phase]}</p>
          }
				</div>
			</div>

			<AnimatePresence>
				{showBubble &&
        <motion.div data-ev-id="ev_50e0171f03"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 10 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="mt-6 rounded-lg p-5"
        style={{
          background: 'var(--theme-surface-2)',
          border: '1px solid var(--theme-border)'
        }}>

						<p data-ev-id="ev_4a469fe9ce" className="text-base" style={{ color: 'var(--theme-fg)' }}>
							{REPLY.slice(0, typed)}
							{phase === 'speaking' &&
            <span data-ev-id="ev_abba8fe8a1"
            aria-hidden="true"
            className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5"
            style={{
              backgroundColor: 'var(--theme-accent)',
              animation: 'caret-blink 1s steps(1) infinite'
            }} />

            }
						</p>
					</motion.div>
        }
			</AnimatePresence>

			{(phase === 'interrupted' || phase === 'done') &&
      <div data-ev-id="ev_e520fb6981" className="mt-6 flex justify-center">
					<button data-ev-id="ev_452cb91971"
        type="button"
        onClick={reset}
        className="inline-flex items-center gap-2 text-sm font-medium transition-colors duration-300"
        style={{ color: 'var(--theme-accent)' }}>

						<RotateCcw size={14} aria-hidden="true" />
						Try again
					</button>
				</div>
      }
		</motion.div>);

}
