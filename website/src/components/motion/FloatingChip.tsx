import type { CSSProperties, ReactNode } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { EASE_OUT } from './Reveal';

type Tone = 'ink' | 'accent' | 'verify';

interface FloatingChipProps {
	children: ReactNode;
	/** Leading dot colour. Ink for facts, accent for live states, verify for outcomes. */
	tone?: Tone;
	delay?: number;
	/** Gentle idle drift. Disabled automatically under reduced motion. */
	float?: boolean;
	className?: string;
	style?: CSSProperties;
}

const DOT: Record<Tone, string> = {
	ink: 'var(--theme-fg)',
	accent: 'var(--theme-accent)',
	verify: 'var(--theme-verify)',
};

/**
 * The floating outcome chip — the Shot 1 device language, translated.
 *
 * A small warm-paper card that sits over the product object at a slight
 * offset and arrives after it, in sequence. It is a labelled fact, never a
 * badge for its own sake: the dot carries the claim's status.
 */
export function FloatingChip({
	children,
	tone = 'ink',
	delay = 0,
	float = true,
	className = '',
	style,
}: FloatingChipProps) {
	const reduced = useReducedMotion();

	return (
		<motion.div
			data-chip=""
			className={`pointer-events-none select-none whitespace-nowrap rounded-full ${className}`}
			style={
				{
					display: 'inline-flex',
					alignItems: 'center',
					gap: 8,
					padding: '9px 16px',
					background: 'var(--theme-surface)',
					border: '1.5px solid var(--theme-border)',
					boxShadow: '0 10px 30px -14px rgba(80, 52, 12, 0.4)',
					fontFamily: 'var(--font-mono)',
					fontSize: '0.68rem',
					letterSpacing: '0.02em',
					color: 'var(--theme-fg)',
					...style,
				} as CSSProperties
			}
			initial={reduced ? { opacity: 0 } : { opacity: 0, y: 14, scale: 0.94 }}
			animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
			transition={{ duration: 0.65, ease: EASE_OUT, delay }}
		>
			{/* The bob is a CSS loop rather than a scripted one: it runs on the
			    compositor, survives a dropped frame, and can be paused wholesale
			    from the hero's off-screen switch. The entrance above stays on the
			    outer node so the two transforms never fight. */}
			<span
				data-ambient-loop={reduced || !float ? undefined : ''}
				className={reduced || !float ? undefined : 'chip-bob'}
				style={
					{
						display: 'inline-flex',
						alignItems: 'center',
						gap: 8,
						'--bob-delay': `${(delay + 0.8).toFixed(2)}s`,
					} as CSSProperties
				}
			>
				<span
					aria-hidden="true"
					style={{
						width: 6,
						height: 6,
						borderRadius: 999,
						background: DOT[tone],
						flex: '0 0 auto',
					}}
				/>
				{children}
			</span>
		</motion.div>
	);
}
