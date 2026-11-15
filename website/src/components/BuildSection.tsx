import { Link } from 'react-router';
import { Container } from '@/components/ui';
import { Reveal, ThreadWave } from '@/components/motion';

/**
 * SESSION 2 — Beat 2, the done-for-you path.
 * The four step cards arrive in a staggered Reveal (delay 0.14·i),
 * the marigold thread continues through the section, and the headline
 * uses the standard Reveal. No ambient loops here — under
 * prefers-reduced-motion the cards simply appear plain.
 */

const STEPS = [
	{
		n: '01',
		title: 'Script call',
		time: '~30 min',
		detail: 'One call: what your callers ask, and what should happen next.',
	},
	{
		n: '02',
		title: 'Build & train',
		time: '2–3 days',
		detail: 'We build the assistant and train it on your scripts.',
	},
	{
		n: '03',
		title: 'Test on your line',
		time: '1 day',
		detail: 'You call it as a customer would. We fix what feels wrong.',
	},
	{
		n: '04',
		title: 'Handover',
		time: 'live',
		detail: 'Running on your number, with a named contact you can reach.',
	},
];

export function BuildSection() {
	return (
		<section
			style={{
				background: 'var(--theme-bg-2)',
				borderTop: '1.5px solid var(--theme-border)',
				borderBottom: '1.5px solid var(--theme-border)',
			}}
		>
			<Container className="py-20 lg:py-28">
				<div className="grid grid-cols-1 gap-y-12 lg:grid-cols-12 lg:gap-x-14">
					{/* Left: the ask */}
					<div className="lg:col-span-6">
						<p
							style={{
								fontFamily: 'var(--font-mono)',
								fontSize: '0.66rem',
								letterSpacing: '0.14em',
								textTransform: 'uppercase',
								color: 'var(--theme-accent)',
							}}
						>
							02 — Done for you
						</p>

						<h2
							className="mt-4"
							style={{
								fontFamily: 'var(--font-display)',
								fontWeight: 800,
								fontSize: 'clamp(2rem, 4.2vw, 3.15rem)',
								lineHeight: 1.02,
								letterSpacing: '-0.03em',
								color: 'var(--theme-fg)',
								maxWidth: '20ch',
							}}
						>
							We build the first one. You take the calls.
						</h2>

						<p
							className="mt-5 max-w-[46ch]"
							style={{ fontSize: '1.05rem', lineHeight: 1.6, color: 'var(--theme-fg-muted)' }}
						>
							Tell us what your callers ask and what should happen next. We build the
							assistant, train it on your scripts, connect your number and hand it over
							working — usually inside a week.
						</p>

						<p
							className="mt-4 max-w-[46ch]"
							style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--theme-fg)' }}
						>
							You own the number and the scripts either way.
						</p>

						<div className="mt-7 flex flex-wrap items-center gap-3">
							<Link
								to="/contact"
								className="inline-flex items-center justify-center font-semibold transition-transform duration-200 hover:-translate-y-0.5"
								style={{
									background: 'var(--theme-fg)',
									color: 'var(--theme-bg)',
									borderRadius: 999,
									padding: '15px 26px',
									fontSize: '0.96rem',
								}}
							>
								Book a build call →
							</Link>

							<Link
								to="/studio"
								className="inline-flex items-center justify-center font-semibold transition-colors duration-200"
								style={{
									background: 'transparent',
									color: 'var(--theme-fg)',
									border: '1.5px solid var(--theme-border-ink)',
									borderRadius: 999,
									padding: '15px 24px',
									fontSize: '0.96rem',
								}}
							>
								Or set it up yourself in 5 minutes →
							</Link>
						</div>
					</div>

					{/* Right: the strip */}
					<div className="lg:col-span-6">
						<ThreadWave amplitude={24} humps={4} strokeWidth={1.6} />

						<ol style={{ borderTop: '1.5px solid var(--theme-border-ink)' }}>
							{STEPS.map((step, i) => (
								<Reveal key={step.n} delay={0.14 * i}>
									<li
										style={{
											display: 'grid',
											gridTemplateColumns: 'auto 1fr auto',
											columnGap: 14,
											rowGap: 4,
											alignItems: 'baseline',
											padding: '16px 0',
											borderBottom: '1.5px solid var(--theme-border)',
										}}
									>
										<span
											style={{
												fontFamily: 'var(--font-mono)',
												fontSize: '0.7rem',
												letterSpacing: '0.08em',
												color: 'var(--theme-accent)',
											}}
										>
											{step.n}
										</span>

										<span
											style={{
												fontFamily: 'var(--font-display)',
												fontWeight: 600,
												fontSize: '1.06rem',
												letterSpacing: '-0.01em',
												color: 'var(--theme-fg)',
											}}
										>
											{step.title}
										</span>

										<span
											style={{
												fontFamily: 'var(--font-mono)',
												fontSize: '0.68rem',
												letterSpacing: '0.04em',
												color: 'var(--theme-fg-muted)',
												whiteSpace: 'nowrap',
											}}
										>
											{step.time}
										</span>

										<span
											style={{
												gridColumn: '2 / 4',
												fontSize: '0.92rem',
												lineHeight: 1.55,
												color: 'var(--theme-fg-muted)',
											}}
										>
											{step.detail}
										</span>

									</li>
									</Reveal>
								))}
						</ol>
					</div>
				</div>

				{/* The hand-off to the impatient reader */}
				<div className="mt-14 flex justify-center">
					<p
						className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1"
						style={{
							fontFamily: 'var(--font-mono)',
							fontSize: '0.68rem',
							letterSpacing: '0.12em',
							textTransform: 'uppercase',
							color: 'var(--theme-fg)',
						}}
					>
						<span>Done-for-you</span>
						<span aria-hidden="true" style={{ color: 'var(--theme-fg-muted)' }}>
							·
						</span>
						<Link
							to="/studio"
							style={{
								color: 'var(--theme-fg-muted)',
								textDecoration: 'underline',
								textDecorationThickness: 2,
								textUnderlineOffset: 4,
							}}
						>
							Self-serve
						</Link>
					</p>
				</div>
			</Container>
		</section>
	);
}

