import { useRef, type CSSProperties, type ReactNode } from 'react';
import { motion, useReducedMotion, useScroll, useSpring, useTransform, type MotionStyle } from 'motion/react';

interface ParallaxProps {
	children: ReactNode;
	/** Total travel across the element's scroll pass, in px. Negative moves against the scroll. */
	distance?: number;
	className?: string;
	style?: CSSProperties;
	/** Spring smoothing. Lower stiffness = lazier drift. */
	stiffness?: number;
}

/**
 * Depth, one axis, one number.
 *
 * The element travels `distance` px across its own pass through the viewport,
 * so adjacent layers separate without ever leaving their section. This is the
 * only mechanism the page uses for depth — no 3D transforms, no perspective
 * hacks, and it costs nothing on layout because it is a paint-time transform.
 */
export function Parallax({
	children,
	distance = 40,
	className = '',
	style,
	stiffness = 110,
}: ParallaxProps) {
	const ref = useRef<HTMLDivElement>(null);
	const reduced = useReducedMotion();

	const { scrollYProgress } = useScroll({
		target: ref,
		offset: ['start end', 'end start'],
	});

	const raw = useTransform(scrollYProgress, [0, 1], [distance, -distance]);
	const smooth = useSpring(raw, { stiffness, damping: 30, mass: 0.4 });

	return (
		<motion.div
			ref={ref}
			className={className}
			style={{ ...style, y: reduced ? 0 : smooth } as MotionStyle}
		>
			{children}
		</motion.div>
	);
}
