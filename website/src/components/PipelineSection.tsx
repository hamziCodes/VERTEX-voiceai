import { useEffect, useRef } from 'react';
import {
	motion,
	useMotionValue,
	useReducedMotion,
	useScroll,
	useSpring,
	useTransform,
	type MotionValue,
} from 'motion/react';
import { Container } from '@/components/ui';
import { Reveal, useAmbientPause } from '@/components/motion';

/**
 * SESSION 5 — Beat 7, the one-stack pipeline (the single dark act).
 *
 * The page's only dark act: `#16120B` full-bleed on cream. Everything else
 * is warm paper. The rail and stage labels are marigold; numbers and state
 * labels are Space Mono. Nothing else on the page is this dark, which is
 * what makes it land.
 *
 * GATE: the four stage numbers are unverified. Per the story's own gate,
 * "If they cannot be shared, remove the per-stage numbers and keep the
 * stage names — on a page explicitly talking to engineers, an invented
 * breakdown is worse than no breakdown." So the numbers are omitted.
 *
 * MOTION: one scroll-driven pass. A single lit chip — the loop itself —
 * travels the rail from VAD to TTS and each stage lights as the chip
 * reaches it, which is the section's whole argument made spatial: the
 * same call never leaves the engine. Progress is read from scroll, not
 * from a timer, so the visitor drives it and it can be read backwards.
 */

const STAGE_NUMERALS = ['07', '08', '09', '10'];
const STAGE_NAMES = ['VAD →', 'STT →', 'LLM →', 'TTS →'];
const STAGE_GLOSS_X_PLACEHOLDER = [
  'Hears you stop talking',
  'Turns speech into text',
  'Decides what to do',
  'Speaks back — and stops when you do',
];

/** Dot, rail and chip all centre on this line, measured from the band's
 *  bottom edge: the dot row is 10px tall, so its centre sits 5px up. */
const RAIL_CENTRE = 5;

const CREAM = '#FFF6E5';

interface StageProps {
	index: number;
	total: number;
	/** 0 → 1 as the chip travels. A plain 1 holds the pipeline fully lit. */
	drive: MotionValue<number>;
	name: string;
	gloss: string;
}

/** One stage: its label, and the mark on the rail that lights when the chip
 *  arrives. Label opacity and dot fill are both derived from the same shared
 *  progress, so they can never disagree about which stage is current. */
function Stage({ index, total, drive, name, gloss }: StageProps) {
	const threshold = total <= 1 ? 0 : index / (total - 1);
	// A short ramp either side of the dot centre: the stage lights as the chip
	// lands on it rather than snapping at an exact pixel. Clamped so the first
	// and last stages reach full brightness at the ends of the rail — the last
	// one has to be fully lit when the chip arrives, or the loop never closes.
	const lo = Math.max(0, threshold - 0.09);
	const hi = Math.min(1, Math.max(lo + 0.01, threshold + 0.02));
	const ramp: [number, number] = [lo, hi];

	const lit = useTransform(drive, ramp, [0.14, 1]);
	const halo = useTransform(drive, ramp, [0, 0.26]);
	const label = useTransform(drive, ramp, [0.6, 1]);

	return (
		<div className="flex h-full flex-col">
			<Reveal delay={0.05 * index} y={14} blur={6} style={{ paddingRight: 10 }}>
				<p
					style={{
						fontFamily: 'var(--font-mono)',
						fontSize: '0.68rem',
						letterSpacing: '0.1em',
						color: CREAM,
					}}
				>
					<motion.span style={{ opacity: label, display: 'inline-block' }}>{name}</motion.span>
				</p>
				<p
					style={{
						marginTop: 6,
						fontSize: '0.62rem',
						lineHeight: 1.45,
						color: 'rgba(255, 246, 229, 0.72)',
					}}
				>
					{gloss}
				</p>
			</Reveal>

			{/* The mark, pushed to the bottom of the column so every dot lands on
			    the rail at the same height whatever the gloss wraps to. */}
			<div style={{ marginTop: 'auto', paddingTop: 18, height: 10, display: 'flex', justifyContent: 'center' }}>
				<span data-stage-dot="" style={{ position: 'relative', display: 'block', width: 9, height: 9 }}>
					<motion.span
						style={{
							position: 'absolute',
							inset: -4,
							borderRadius: 999,
							background: CREAM,
							filter: 'blur(5px)',
							opacity: halo,
						}}
					/>
					<span
						style={{
							position: 'absolute',
							inset: 0,
							borderRadius: 999,
							border: '1.5px solid rgba(255, 246, 229, 0.3)',
						}}
					/>
					<motion.span
						style={{
							position: 'absolute',
							inset: 0,
							borderRadius: 999,
							background: CREAM,
							opacity: lit,
						}}
					/>
				</span>
			</div>
		</div>
	);
}

export function PipelineSection() {
	const reduced = useReducedMotion() ?? false;
	const sectionRef = useRef<HTMLElement | null>(null);
	const railRef = useRef<HTMLDivElement>(null);
	const chipRef = useRef<HTMLDivElement>(null);

	// The rail's ambient shimmer is the one looping thing in this act; it stops
	// when the section leaves the viewport or the tab is hidden.
	useAmbientPause(sectionRef);

	// 0 when the rail's top reaches 85% of the viewport, 1 when its end passes
	// 55% — so the pipeline completes while the reader is looking at it.
	const { scrollYProgress } = useScroll({ target: railRef, offset: ['start 85%', 'end 55%'] });
	const progress = useSpring(scrollYProgress, { stiffness: 80, damping: 22, mass: 0.35 });

	// Reduced motion gets a still, fully lit pipeline: no travel, nothing to
	// follow. The chip rests at TTS and every stage is on.
	const still = useMotionValue(1);
	const drive = reduced ? still : progress;

	// Chip travel is measured in pixels because a percentage translate would be
	// relative to the chip itself, not the rail. Measured once, then kept honest
	// by a ResizeObserver and by the chip's own width (it changes if the label
	// font loads late).
	const chipX = useMotionValue(0);
	useEffect(() => {
		const place = () => {
			const rail = railRef.current;
			const chip = chipRef.current;
			if (!rail || !chip) return;
			const width = rail.clientWidth;
			const chipWidth = chip.offsetWidth;
			const from = width * 0.125 - chipWidth / 2;
			const to = width * 0.875 - chipWidth / 2;
			chipX.set(from + (to - from) * (reduced ? 1 : progress.get()));
		};

		place();
		const stop = progress.on('change', place);
		const observer = new ResizeObserver(place);
		if (railRef.current) observer.observe(railRef.current);
		if (chipRef.current) observer.observe(chipRef.current);

		return () => {
			stop();
			observer.disconnect();
		};
	}, [progress, chipX, reduced]);

	return (
		<section
			ref={sectionRef}
			data-ambient="live"
			style={{ background: '#16120B', borderTop: '1.5px solid var(--theme-border)', borderBottom: '1.5px solid var(--theme-border)', paddingBottom: '40px' }}
		>
			<Container className="py-16 lg:py-20 pb-12">
				<div className="relative flex flex-col gap-6 min-h-[400px]">
					<p
						className="text-lg font-semibold"
						style={{ color: '#B45309', fontFamily: 'var(--font-display)', lineHeight: 1.02 }}
					>
						07 — One stack: the pipeline
					</p>
					<h2
						className="text-2xl font-serif font-medium leading-none tracking-[-0.03em]"
						style={{ color: '#FFF6E5' }}
					>
						One engine. Four jobs. No hand-offs.
					</h2>
					<p
						className="mt-3 max-w-2xl opacity-70"
						style={{
							color: '#FFF6E5',
							fontSize: '1.04rem',
							lineHeight: 1.6,
						}}
					>
						Most voice agents stitch together four vendors. Every seam is a delay, and none of them are built to be interrupted. This is one loop.
					</p>

					{/* The rail. Four stage columns share a grid so their marks line up
					    on one line whatever their glosses wrap to; the lit chip, the
					    fill and the shimmer are absolutely positioned on that line. */}
					<div ref={railRef} className="relative" style={{ marginTop: 28 }}>
						<div className="grid grid-cols-4">
							{STAGE_NAMES.map((name, i) => (
								<Stage
									key={name}
									index={i}
									total={STAGE_NAMES.length}
									drive={drive}
									name={name}
									gloss={STAGE_GLOSS_X_PLACEHOLDER[i]}
								/>
							))}
						</div>

						{/* Decorative: the stage list above already carries this meaning. */}
						<div aria-hidden="true">
							{/* The unlit rail, held back to a hairline so the lit pass reads. */}
							<div
								data-pipeline-rail=""
								style={{
									position: 'absolute',
									left: 0,
									right: 0,
									bottom: RAIL_CENTRE - 1,
									height: 2,
									borderRadius: 999,
									background: 'rgba(255, 246, 229, 0.14)',
								}}
							/>

							{/* The travelled portion — dot one to dot four. */}
							<motion.div
								data-pipeline-fill=""
								style={{
									position: 'absolute',
									left: '12.5%',
									right: '12.5%',
									bottom: RAIL_CENTRE - 1,
									height: 2,
									borderRadius: 999,
									background: '#B45309',
									transformOrigin: '0 50%',
									scaleX: reduced ? 1 : progress,
								}}
							/>

							{/* Ambient pass: a slow breath of cream running the rail so the
							    act is alive before anyone scrolls it. Transform only. */}
							{!reduced && (
								<span
									data-ambient-loop=""
									style={{
										position: 'absolute',
										left: 0,
										bottom: RAIL_CENTRE - 1,
										width: '20%',
										height: 2,
										background: `linear-gradient(90deg, rgba(255,246,229,0), ${CREAM}, rgba(255,246,229,0))`,
										opacity: 0.22,
										animation: 'rail-shimmer 9s linear infinite',
									}}
								/>
							)}

							{/* The loop itself. Sits on the line, not above it. */}
							<motion.div
								ref={chipRef}
								data-loop-chip=""
								style={{
									position: 'absolute',
									left: 0,
									bottom: RAIL_CENTRE - 10,
									x: chipX,
									height: 20,
									display: 'flex',
									alignItems: 'center',
									padding: '0 9px',
									borderRadius: 999,
									border: `1.5px solid ${CREAM}`,
									background: '#16120B',
									color: CREAM,
									fontFamily: 'var(--font-mono)',
									fontSize: '0.55rem',
									letterSpacing: '0.12em',
									textTransform: 'uppercase',
									whiteSpace: 'nowrap',
									boxShadow: '0 0 0 6px rgba(22, 18, 11, 0.9)',
								}}
							>
								<span>one loop</span>
							</motion.div>
						</div>
					</div>
				</div>
			</Container>
		</section>
	);
}
