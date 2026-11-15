import { useId } from 'react';
import { useReducedMotion } from 'motion/react';

interface ThreadWaveProps {
	/** True while a line is "playing" — the pulse travels the thread. */
	active?: boolean;
	className?: string;
	style?: React.CSSProperties;
	/** Path height in user units; the SVG scales to its box. */
	amplitude?: number;
	/** Number of humps across the full width. */
	humps?: number;
	strokeWidth?: number;
}

const W = 640;
const H = 160;
const STEPS = 160;

/** A single tapered thread: amplitude eases in from both ends so it reads as
 *  one continuous line leaving and returning to the page, not a clipped sine. */
function threadPath(humps: number, amplitude: number) {
	const pts: string[] = [];
	for (let i = 0; i <= STEPS; i += 1) {
		const t = i / STEPS;
		const x = t * W;
		const taper = Math.sin(Math.PI * t) ** 0.7;
		const y = H / 2 + Math.sin(t * Math.PI * 2 * humps) * amplitude * taper;
		pts.push(`${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`);
	}
	return pts.join(' ');
}

/**
 * The marigold thread — the page's waveform motif.
 *
 * One line, drawn once, a pulse of light running along it while Wavia is
 * speaking. It sits behind the product object rather than inside it, so the
 * demo card keeps its own honest trace and the thread carries brand, not data.
 * Under reduced motion the pulse is removed and the thread is simply a line.
 */
export function ThreadWave({
	active = false,
	className = '',
	style,
	amplitude = 30,
	humps = 5,
	strokeWidth = 2,
}: ThreadWaveProps) {
	const reduced = useReducedMotion();
	const uid = useId().replace(/:/g, '');
	const d = threadPath(humps, amplitude);
	const pulsing = active && !reduced;

	return (
		<svg
			viewBox={`0 0 ${W} ${H}`}
			preserveAspectRatio="none"
			className={className}
			style={{ display: 'block', width: '100%', height: '100%', overflow: 'visible', ...style }}
			aria-hidden="true"
			focusable="false"
		>
			<defs>
				<linearGradient id={`thread-fade-${uid}`} x1="0" y1="0" x2="1" y2="0">
					<stop offset="0%" stopColor="var(--theme-accent)" stopOpacity="0" />
					<stop offset="22%" stopColor="var(--theme-accent)" stopOpacity="0.85" />
					<stop offset="78%" stopColor="var(--theme-accent)" stopOpacity="0.85" />
					<stop offset="100%" stopColor="var(--theme-accent)" stopOpacity="0" />
				</linearGradient>
			</defs>

			<path
				d={d}
				fill="none"
				stroke={`url(#thread-fade-${uid})`}
				strokeWidth={strokeWidth + 0.5}
				strokeLinecap="round"
				vectorEffect="non-scaling-stroke"
			/>

			{/* Ambient pass: a soft segment always travelling the thread, so the
			    hero is lit at rest. Slow enough to read as drift, not activity. */}
			<path
				d={d}
				fill="none"
				stroke="var(--theme-accent)"
				strokeWidth={strokeWidth + 1}
				strokeLinecap="round"
				vectorEffect="non-scaling-stroke"
				data-ambient-loop={reduced ? undefined : ''}
				style={{
					strokeDasharray: '150 900',
					opacity: active ? 0.42 : 0.26,
					animation: reduced ? undefined : 'thread-ambient 11s linear infinite',
					transition: 'opacity 600ms ease-out',
				}}
			/>

			{/* The speak pulse: a short bright segment runs the thread fast while
			    Wavia is mid-sentence. Absent at rest — the ambient pass covers that. */}
			<path
				d={d}
				fill="none"
				stroke="var(--theme-accent)"
				strokeWidth={strokeWidth + 1.5}
				strokeLinecap="round"
				vectorEffect="non-scaling-stroke"
				style={{
					strokeDasharray: '56 900',
					opacity: pulsing ? 0.9 : 0,
					animation: pulsing ? 'thread-travel 2.6s linear infinite' : undefined,
					transition: 'opacity 400ms ease-out',
				}}
			/>
		</svg>
	);
}
