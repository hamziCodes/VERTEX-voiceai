import type { CSSProperties, ReactNode } from 'react';
import { motion, useReducedMotion } from 'motion/react';

/**
 * Reveal primitives — the page's one entrance vocabulary.
 *
 * Everything on the page arrives the same way: out of its own mask, slightly
 * blurred, settling onto the baseline. No bounce, no spring overshoot, no
 * opacity-only fade — a fade alone reads as "web template", a mask reads as
 * print coming off a press.
 *
 * `prefers-reduced-motion` collapses every variant to a plain fade. Nothing
 * translates, scales or blurs for those visitors.
 */

export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

interface RevealProps {
	children: ReactNode;
	delay?: number;
	duration?: number;
	/** Distance the content travels up into place, in px. */
	y?: number;
	/** Starting blur radius, in px. 0 disables the blur. */
	blur?: number;
	className?: string;
	style?: CSSProperties;
	/** Play on mount instead of on scroll into view. */
	onMount?: boolean;
}

/** Block-level reveal for paragraphs, cards and panels. */
export function Reveal({
	children,
	delay = 0,
	duration = 0.8,
	y = 22,
	blur = 8,
	className = '',
	style,
	onMount = false,
}: RevealProps) {
	const reduced = useReducedMotion();

	const target = { opacity: 1, y: 0, filter: 'blur(0px)' };
	const initial = { opacity: 0, y: reduced ? 0 : y, filter: reduced ? 'blur(0px)' : `blur(${blur}px)` };
	const transition = { duration, ease: EASE_OUT, delay };

	if (onMount) {
		return (
			<motion.div
				className={className}
				style={style}
				initial={initial}
				animate={target}
				transition={transition}
			>
				{children}
			</motion.div>
		);
	}

	return (
		<motion.div
			className={className}
			style={style}
			initial={initial}
			whileInView={target}
			viewport={{ once: true, margin: '-10% 0px' }}
			transition={transition}
		>
			{children}
		</motion.div>
	);
}

interface MaskLineProps {
	children: ReactNode;
	delay?: number;
	duration?: number;
	className?: string;
	innerClassName?: string;
}

/**
 * One masked line of type. The line is clipped by its own box and rises into
 * it, so the entrance belongs to the letterforms rather than the block.
 * Padding + negative margin keep descenders and periods from being shaved.
 */
export function MaskLine({
	children,
	delay = 0,
	duration = 0.9,
	className = '',
	innerClassName = '',
}: MaskLineProps) {
	const reduced = useReducedMotion();

	return (
		<span
			className={`block overflow-hidden ${className}`}
			style={{ paddingBottom: '0.14em', marginBottom: '-0.14em' }}
		>
			<motion.span
				className={`block ${innerClassName}`}
				initial={reduced ? { opacity: 0 } : { y: '112%', opacity: 0, filter: 'blur(10px)' }}
				animate={reduced ? { opacity: 1 } : { y: '0%', opacity: 1, filter: 'blur(0px)' }}
				transition={{ duration, ease: EASE_OUT, delay }}
				style={{ willChange: reduced ? undefined : 'transform, filter' }}
			>
				{children}
			</motion.span>
		</span>
	);
}

interface MaskWordProps {
	children: ReactNode;
	delay?: number;
	duration?: number;
	className?: string;
}

/**
 * One display word, for headlines that must wrap word-by-word.
 *
 * Deliberately *not* overflow-hidden: display leading is tighter than the
 * glyph ink (a 0.86 line-height clips a 'p' descender), so the word rises on a
 * blur instead of through a mask. At this size the blur is the mask.
 */
export function MaskWord({ children, delay = 0, duration = 1, className = '' }: MaskWordProps) {
	const reduced = useReducedMotion();

	return (
		<motion.span
			className={`inline-block align-bottom ${className}`}
			initial={reduced ? { opacity: 0 } : { y: '0.55em', opacity: 0, filter: 'blur(14px)' }}
			animate={reduced ? { opacity: 1 } : { y: '0em', opacity: 1, filter: 'blur(0px)' }}
			transition={{ duration, ease: EASE_OUT, delay }}
			style={{ willChange: reduced ? undefined : 'transform, filter' }}
		>
			{children}
		</motion.span>
	);
}
