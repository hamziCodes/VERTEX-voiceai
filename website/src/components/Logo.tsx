import { Link } from 'react-router';

/**
 * Theme B brand mark — "The Thread".
 *
 * One marigold line that enters as a dot, rises into two hand-threaded loops
 * (the second taller than the first), and lands in a dot. Control points are
 * deliberately off-centre so it reads drawn, not geometric — a printed stamp,
 * not a pictogram. The brand kit's five-bar waveform is gone on purpose: five
 * bars is the universal voice-AI mark and it says "audio file", not
 * "turn-taking", which is the actual product difference.
 *
 * Below 24px the thread drops and the mark becomes a marigold dot plus a
 * half-circle arc, which stays legible at favicon size.
 */

const THREAD =
	'M5 12 C8 12 8 8.2 12 8.2 C16 8.2 14.6 18.6 19 18.6 C23.4 18.6 22 3.4 28 3.4 C32 3.4 32 12 35 12';

export function ThreadMark({
	height = 24,
	className = '',
	animate = true,
}: {
	height?: number;
	className?: string;
	animate?: boolean;
}) {
	const simple = height < 24;

	if (simple) {
		return (
			<svg
				viewBox="0 0 24 24"
				width={height}
				height={height}
				className={className}
				aria-hidden="true"
				focusable="false"
			>
				<circle cx="7" cy="12" r="3.2" fill="var(--theme-accent)" />
				<path
					d="M11.5 5.6 A8 8 0 0 1 11.5 18.4"
					fill="none"
					stroke="var(--theme-accent)"
					strokeWidth="2.4"
					strokeLinecap="round"
				/>
			</svg>
		);
	}

	return (
		<svg
			viewBox="0 0 40 24"
			width={(height / 24) * 40}
			height={height}
			className={className}
			aria-hidden="true"
			focusable="false"
		>
			{/* Entry dot */}
			<circle cx="3.2" cy="12" r="2.6" fill="var(--theme-accent)" />
			{/* The thread */}
			<path
				d={THREAD}
				fill="none"
				stroke="var(--theme-accent)"
				strokeWidth="2.5"
				strokeLinecap="round"
				strokeLinejoin="round"
				pathLength={64}
				strokeDasharray={64}
				style={
					animate
						? { animation: 'thread-draw 1.1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards' }
						: { strokeDashoffset: 0 }
				}
			/>
			{/* Exit dot */}
			<circle cx="36.8" cy="12" r="3" fill="var(--theme-accent)" />
		</svg>
	);
}

/** The wordmark on its own, for the footer's giant lockup. */
export function Wordmark({
	className = '',
	style,
	dotColor = 'var(--theme-accent)',
}: {
	className?: string;
	style?: React.CSSProperties;
	dotColor?: string;
}) {
	return (
		<span
			className={`font-display lowercase inline-flex items-baseline ${className}`}
			style={{ letterSpacing: '-0.05em', lineHeight: 0.82, ...style }}
		>
			<span>wavia</span>
			<span
				aria-hidden="true"
				className="inline-block rounded-full"
				style={{
					width: '0.16em',
					height: '0.16em',
					marginLeft: '0.06em',
					background: dotColor,
					animation: 'dot-pulse 3s ease-in-out infinite',
					flexShrink: 0,
				}}
			/>
		</span>
	);
}

interface LogoProps {
	size?: 'sm' | 'md' | 'lg';
	asLink?: boolean;
	className?: string;
}

export function Logo({ size = 'md', asLink = true, className = '' }: LogoProps) {
	const markHeight = size === 'lg' ? 44 : size === 'sm' ? 18 : 24;
	const fontSize = size === 'lg' ? 'text-4xl lg:text-5xl' : size === 'sm' ? 'text-lg' : 'text-2xl';
	const weight = size === 'lg' ? 800 : 700;

	const content = (
		<span className={`inline-flex items-center select-none ${className}`} style={{ gap: markHeight / 2 }}>
			<ThreadMark height={markHeight} />
			<span
				className={`font-display lowercase inline-flex items-baseline ${fontSize}`}
				style={{ color: 'var(--theme-fg)', letterSpacing: '-0.05em', lineHeight: 1, fontWeight: weight }}
			>
				<span>wavia</span>
				<span
					aria-hidden="true"
					className="inline-block rounded-full"
					style={{
						width: '0.16em',
						height: '0.16em',
						marginLeft: '0.06em',
						background: 'var(--theme-accent)',
						animation: 'dot-pulse 3s ease-in-out infinite',
						flexShrink: 0,
					}}
				/>
			</span>
		</span>
	);

	if (asLink) {
		return (
			<Link to="/" aria-label="Wavia — home" className="inline-flex items-center">
				{content}
			</Link>
		);
	}

	return content;
}
