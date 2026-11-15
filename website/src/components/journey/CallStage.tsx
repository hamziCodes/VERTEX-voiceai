/**
 * The call card — the persistent object of the immersive homepage.
 *
 * This component is presentational only. It renders the call in its FINAL,
 * fully-readable state: every transcript line, both call states and the
 * interruption group are in the DOM and visible. CallJourney's GSAP timeline
 * sets the hidden/offset states and scrubs them; under prefers-reduced-motion
 * (or with no JS) nothing is set, so the card simply reads top to bottom.
 *
 * The script is the demo's own clinic call (src/content/demo.ts): the Urdu
 * greeting, the ask, "Thursday, ten.", the booking, and the interruption —
 * dramatised, and labelled scripted in the card head, exactly like the demo.
 */

const BAR_COUNT = 36;

// Deterministic pseudo-random heights, same recipe as the demo trace, so the
// waveform looks drawn rather than generated differently on every render.
const BARS = Array.from({ length: BAR_COUNT }, (_, i) => {
	const n = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1;
	return 0.18 + n * 0.82;
});

function Speaker({ who }: { who: 'wavia' | 'caller' }) {
	return (
		<span
			style={{
				fontFamily: 'var(--font-mono)',
				fontSize: '0.6rem',
				letterSpacing: '0.12em',
				textTransform: 'uppercase',
				color: who === 'wavia' ? 'var(--theme-accent)' : 'var(--theme-fg-muted)',
			}}
		>
			{who}
		</span>
	);
}

export function CallStage() {
	return (
		<div className="j-cardwrap">
			{/* Stacked paper edges — the same object vocabulary as the old hero. */}
			<div aria-hidden="true" className="j-edge j-edge-2" />
			<div aria-hidden="true" className="j-edge j-edge-1" />

			<div className="j-card">
				{/* Head: call state (ringing → on call) + the honesty label. */}
				<div className="j-card-head">
					<div className="j-states">
						<span className="j-state j-state-ring">
							<span className="j-ringdot">
								<span aria-hidden="true" className="j-halo j-halo-1" />
								<span aria-hidden="true" className="j-halo j-halo-2" />
								<span className="j-dot" />
							</span>
							Clinic line · incoming call
						</span>
						<span className="j-state j-state-live">
							<span className="j-dot j-dot-live" />
							On call · 00:12
						</span>
					</div>
					<span className="j-scripted">Scripted · no audio yet</span>
				</div>

				{/* Waveform strip. GSAP scrubs the bars (speaking, then the
				    Scene 3 flatline); the container's slow opacity breath is CSS. */}
				<div className="j-wave" aria-hidden="true">
					{BARS.map((h, i) => (
						<span key={i} style={{ height: Math.round(h * 40) }} />
					))}
				</div>

				{/* Transcript body. Two groups crossfade: the main call, and the
				    interruption replay that gets its own scene. */}
				<div className="j-body">
					<div className="j-lines j-lines-main">
						<div className="j-line" data-line="greeting">
							<Speaker who="wavia" />
							<p className="urdu j-urdu" lang="ur" dir="rtl">
								السلام علیکم، یہ کلینک ہے۔ میں آپ کی کیا مدد کر سکتا ہوں؟
							</p>
						</div>
						<div className="j-line" data-line="ask">
							<Speaker who="caller" />
							<p>I&rsquo;d like an appointment tomorrow.</p>
						</div>
						<div className="j-line" data-line="slots">
							<Speaker who="wavia" />
							<p>Tomorrow at ten in the morning or four in the afternoon — which suits you?</p>
						</div>
						<div className="j-line" data-line="thursday">
							<Speaker who="caller" />
							<p>Thursday, ten.</p>
						</div>
						<div className="j-line j-line-booked" data-line="booked">
							<span aria-hidden="true" className="j-hl" />
							<Speaker who="wavia" />
							<p>Booked. I have sent you a confirmation message.</p>
						</div>
					</div>

					<div className="j-lines j-lines-cut">
						<div className="j-line">
							<Speaker who="wavia" />
							<p className="j-cutline">Tomorrow at ten in the morning or four in the after—</p>
						</div>
						<div className="j-line">
							<Speaker who="caller" />
							<p>Wait — I said Thursday.</p>
						</div>
						<span className="j-cut-chip">interrupted at 0.4s</span>
					</div>
				</div>
			</div>
		</div>
	);
}
