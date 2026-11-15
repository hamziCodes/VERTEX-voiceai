import { useEffect, useMemo, useRef, useState } from 'react';

export type WaveState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface WaveformProps {
  state: WaveState;
  height?: number;
  barCount?: number;
  barWidth?: number;
  gap?: number;
  className?: string;
  label?: string;
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  return reduced;
}

const STATE_LABEL: Record<WaveState, string> = {
  idle: 'Waveform idle',
  listening: 'Waveform listening',
  thinking: 'Waveform thinking',
  speaking: 'Waveform speaking'
};

export function Waveform({
  state,
  height = 80,
  barCount = 9,
  barWidth = 6,
  gap = 6,
  className = '',
  label
}: WaveformProps) {
  const reduced = usePrefersReducedMotion();
  const [levels, setLevels] = useState<number[]>(() => Array(barCount).fill(0.4));
  const timerRef = useRef<number | null>(null);

  const accentColor = 'var(--theme-accent)';
  const accentHover = 'var(--theme-accent-hover)';
  const successColor = 'var(--theme-verify)';

  useEffect(() => {
    if (state !== 'listening' || reduced) {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    const tick = () =>
    setLevels(Array.from({ length: barCount }, () => 0.2 + Math.random() * 0.7));

    tick();
    timerRef.current = window.setInterval(tick, 150);

    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [state, barCount, reduced]);

  const bars = useMemo(() => Array.from({ length: barCount }, (_, i) => i), [barCount]);

  const isThinking = state === 'thinking';
  const dotSize = Math.max(6, Math.round(height * 0.15));
  const width = barCount * barWidth + (barCount - 1) * gap;

  return (
    <div data-ev-id="ev_1fa8bd9d9d"
    className={`relative flex items-center justify-center ${className}`}
    style={{ height, width }}
    role="img"
    aria-label={label ?? STATE_LABEL[state]}>

			<div data-ev-id="ev_be95981d11"
      className="flex items-center justify-center transition-opacity duration-300"
      style={{ gap, height, opacity: isThinking ? 0 : 1 }}
      aria-hidden="true">

				{bars.map((i) => {
          const style: React.CSSProperties = {
            width: barWidth,
            height: '100%',
            borderRadius: Math.min(4, barWidth / 2),
            transformOrigin: 'center',
            backgroundColor: state === 'listening' ? accentHover : accentColor,
            transition: 'background-color 300ms ease-out, transform 150ms ease-out'
          };

          if (reduced) {
            style.transform = `scaleY(${state === 'idle' ? 0.2 : 0.6})`;
          } else if (state === 'listening') {
            style.transform = `scaleY(${levels[i] ?? 0.3})`;
          } else if (state === 'speaking') {
            style.animation = `speaking-wave 1.2s ease-in-out ${(-(i * 1.2) / barCount).toFixed(3)}s infinite`;
          } else {
            style.animation = `idle-breathe 2.4s ease-in-out ${((i % barCount) * 0.16).toFixed(2)}s infinite`;
          }

          return <span data-ev-id="ev_e2fdf9f734" key={i} style={style} />;
        })}
			</div>

			<span data-ev-id="ev_66f1be4cf0"
      aria-hidden="true"
      className="absolute transition-opacity duration-300"
      style={{
        width: dotSize,
        height: dotSize,
        borderRadius: 999,
        backgroundColor: successColor,
        opacity: isThinking ? 1 : 0,
        animation: isThinking && !reduced ? 'thinking-pulse 0.8s ease-in-out infinite' : undefined
      }} />

		</div>);

}
