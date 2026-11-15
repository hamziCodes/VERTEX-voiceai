import { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react';
import { Container } from '@/components/ui';
import { ThreadWave, useAmbientPause } from '@/components/motion';

/**
 * SESSION 4 — Beat 5, the trailer.
 *
 * Hard gate: no footage exists. The story's rule for that case is absolute —
 * "Until then the play control is visibly disabled and the fallback line is
 * visible", and a stock AI-voice clip "would be the most damaging thing on this
 * site". So this ships as a poster-only slate that says, in its own chrome, that
 * the take has not been recorded.
 *
 * No black band. The dark act belongs to Beat 7 alone, so the poster is a cream
 * panel on paper carrying the page's second — and last — shadow.
 *
 * The poster is not a photograph and does not pretend to be one: it is a film
 * slate, which is the honest visual for "this is where the take goes".
 *
 * The slate carries the page's thread — one slow pass across it, low and soft,
 * sitting behind the disabled control. It is the only thing on the slate that
 * moves, and it stops with the section. Nothing here suggests playability.
 */

const TICKS = Array.from({ length: 56 }, (_, i) => i);

export function TrailerSection() {
	const reduced = useReducedMotion() ?? false;
	const ref = useRef<HTMLDivElement>(null);
	const sectionRef = useRef<HTMLElement | null>(null);

	// One ambient loop lives on this slate; it pauses when the section leaves the
	// viewport or the tab is hidden, and is absent entirely under reduced motion.
	useAmbientPause(sectionRef);

	// Scroll-scrubbed 1.0 → 1.04 as the poster crosses the viewport. Motion only;
	// nothing about it implies the clip is playable.
	const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
	const scale = useTransform(scrollYProgress, [0, 1], [1, 1.04]);

	return (
		<section ref={sectionRef} data-ambient="live" style={{ borderTop: '1.5px solid var(--theme-border)' }}>
			<Container className="py-20 lg:py-28">
				<div className="flex flex-col gap-3">
					<p
						style={{
							fontFamily: 'var(--font-mono)',
							fontSize: '0.66rem',
							letterSpacing: '0.14em',
							textTransform: 'uppercase',
							color: 'var(--theme-accent)',
						}}
					>
						05 — The call
					</p>

					<p
						className="max-w-[58ch]"
						style={{ fontSize: '1.05rem', lineHeight: 1.6, color: 'var(--theme-fg)' }}
					>
						A real inbound call, <strong>60–90 seconds</strong>, unedited. The caller
						interrupts twice; the booking still lands in the calendar.
					</p>
				</div>

				<div ref={ref} className="mt-9">
					<motion.div
						style={{
							scale: reduced ? 1 : scale,
							position: 'relative',
							// A 16/9 box with a 220px floor cannot go below ~391px wide, which
							// pushed the whole page sideways on small phones. Let it yield.
							aspectRatio: '16 / 9',
							minHeight: 220,
							maxWidth: '100%',
							borderRadius: 32,
							border: '1.5px solid var(--theme-border)',
							background: 'var(--theme-surface-2)',
							boxShadow: 'var(--theme-shadow)',
							overflow: 'hidden',
							display: 'grid',
							placeItems: 'center',
						}}
					>
						{/* Slate header */}
						<div
							className="absolute inset-x-0 top-0 flex items-center justify-between gap-3"
							style={{
								padding: '14px 18px',
								fontFamily: 'var(--font-mono)',
								fontSize: '0.6rem',
								letterSpacing: '0.12em',
								textTransform: 'uppercase',
								color: 'var(--theme-fg-muted)',
							}}
						>
							<span>SC-05 · Inbound · Unedited</span>
							<span className="hidden sm:inline">Take not recorded</span>
						</div>

						{/* The thread, across the slate and behind its control. Low enough
						    to read as brand texture, never as playback. */}
						<div
							aria-hidden="true"
							style={{
								position: 'absolute',
								left: 0,
								right: 0,
								top: '20%',
								height: '26%',
								opacity: 0.4,
								pointerEvents: 'none',
							}}
						>
							<ThreadWave amplitude={24} humps={4} strokeWidth={1.6} />
						</div>

						{/* Play control — visibly disabled, not a mystery button */}
						<div className="flex flex-col items-center gap-3">
							<button
								type="button"
								disabled
								aria-disabled="true"
								title="Footage in production"
								style={{
									width: 62,
									height: 62,
									borderRadius: 999,
									border: '1.5px solid var(--theme-border)',
									background: 'transparent',
									color: 'var(--theme-fg-muted)',
									opacity: 0.55,
									cursor: 'not-allowed',
									display: 'grid',
									placeItems: 'center',
								}}
							>
								<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
									<path d="M5 3.5 12.5 8 5 12.5Z" fill="currentColor" />
								</svg>
							</button>

							<p
								style={{
									fontFamily: 'var(--font-mono)',
									fontSize: '0.58rem',
									letterSpacing: '0.14em',
									textTransform: 'uppercase',
									color: 'var(--theme-fg-muted)',
									textAlign: 'center',
								}}
							>
								Footage in production
							</p>
						</div>

						{/* Timestamp ruler along the bottom edge */}
						<div
							className="absolute inset-x-0 bottom-0 hidden items-end gap-[2px] sm:flex"
							style={{ padding: '0 18px 12px', height: 42 }}
							aria-hidden="true"
						>
							{TICKS.map((i) => (
								<span
									key={i}
									style={{
										flex: '1 1 0',
										height: i % 7 === 0 ? 12 : i % 3 === 0 ? 7 : 4,
										background: 'var(--theme-border)',
										borderRadius: 1,
									}}
								/>
							))}
						</div>

						{/* The clock, at zero, because there is no take to count */}
						<div
							className="absolute bottom-0 right-0"
							style={{
								padding: '12px 18px',
								fontFamily: 'var(--font-mono)',
								fontSize: '0.6rem',
								letterSpacing: '0.1em',
								color: 'var(--theme-fg-muted)',
							}}
						>
							00:00 / 01:20
						</div>
					</motion.div>
				</div>

				<p
					className="mt-5 max-w-[52ch]"
					style={{ fontSize: '0.92rem', lineHeight: 1.6, color: 'var(--theme-fg-muted)' }}
				>
					Footage in production — hear the same call in{' '}
					<a
						href="#demo"
						style={{
							color: 'var(--theme-fg)',
							textDecoration: 'underline',
							textDecorationThickness: 2,
							textUnderlineOffset: 3,
						}}
					>
						the demo above
					</a>
					.
				</p>
			</Container>
		</section>
	);
}
