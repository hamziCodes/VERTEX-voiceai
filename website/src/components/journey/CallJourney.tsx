import { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { CallStage } from './CallStage';

gsap.registerPlugin(ScrollTrigger);

/**
 * Scenes 0–4 of the immersive homepage (docs/design/IMMERSIVE_SCENARIO.md).
 *
 * One persistent object — the call — on one pinned stage. Scroll scrubs the
 * whole voyage: land → the ring → the conversation flows out into three
 * callouts → the interruption → the booking docks into a CRM record. The
 * interactive demo below this section is the visitor's turn (Scene 5); this
 * component never touches it.
 *
 * Everything animates transform / opacity / stroke only. The DOM is authored
 * in its final readable state: if GSAP never runs, or the visitor prefers
 * reduced motion, the root gains `journey--static` and the scenes stack as
 * plain, fully-visible blocks with no pinning.
 */

const CALLOUTS = [
	{
		tick: '01 · the greeting',
		text: 'In Urdu. Not translated later — spoken first.',
		sub: 'also english · العربية · bahasa melayu',
	},
	{ tick: '02 · the ask', text: 'It understands the ask.', sub: null },
	{ tick: '03 · the booking', text: 'It books it.', sub: null },
];

const CRM_FIELDS = [
	{ k: 'Caller', v: 'Clinic line' },
	{ k: 'Booked', v: 'Thursday · 10:00' },
	{ k: 'Confirmation', v: 'Sent' },
];

export function CallJourney() {
	const rootRef = useRef<HTMLElement | null>(null);

	useLayoutEffect(() => {
		const root = rootRef.current;
		if (!root) return;

		// Reduced motion: no pin, no scrub — the static CSS takes over and
		// every scene renders in its final state.
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
			root.classList.add('journey--static');
			return;
		}

		const ctx = gsap.context(() => {
			const mm = gsap.matchMedia();

			mm.add(
				{
					desktop: '(min-width: 1024px)',
					mobile: '(max-width: 1023px)',
				},
				(mctx) => {
					const isDesktop = Boolean(mctx.conditions?.desktop);
					const q = gsap.utils.selector(root);

					const inner = q('.j-inner')[0] as HTMLElement;
					const stagecol = q('.j-stagecol');
					const cardW = () => (isDesktop ? 420 : inner.clientWidth - 40);
					// x offsets that move the stage from its CSS home (right side)
					// to centre stage, then to the left dock. Mobile: no travel.
					const xCenter = () => (isDesktop ? 24 + cardW() / 2 - inner.clientWidth / 2 : 0);
					const xDock = () => (isDesktop ? 48 + cardW() - inner.clientWidth : 0);
					const liftTravel = () => inner.clientWidth - 344 - 500;

					const bars = q('.j-wave span');
					const speaking = (i: number) => 0.45 + ((i * 37) % 55) / 100;

					/* ── Initial states (GSAP-only; the no-JS/reduced page is
					      authored visible and never passes through here). ── */
					gsap.set(q('.j-dim'), { opacity: 0 });
					gsap.set(q('.j-state-live'), { opacity: 0 });
					gsap.set(q('.j-halo'), { opacity: 0, scale: 0.5, transformOrigin: 'center' });
					gsap.set(q('.j-line'), { opacity: 0, y: 14 });
					gsap.set(q('.j-lines-cut'), { opacity: 0 });
					gsap.set(q('.j-lines-cut .j-line'), { opacity: 1, y: 0 });
					gsap.set(q('.j-cutline'), { textDecorationColor: 'rgba(28, 20, 8, 0)' });
					gsap.set(q('.j-cut-chip'), { opacity: 0, scale: 0.9 });
					gsap.set(q('.j-callout'), { opacity: 0, y: 24 });
					gsap.set(q('.j-callout-rule'), { scaleX: 0, transformOrigin: 'left center' });
					gsap.set(q('.j-lift'), { opacity: 0, y: isDesktop ? 0 : 26 });
					gsap.set(q('.j-crm'), { opacity: 0, x: isDesktop ? 40 : 0, y: isDesktop ? 0 : 24 });
					gsap.set(q('.j-field'), { opacity: 0, scale: 1.12, y: 6, transformOrigin: 'left center' });
					// The thread is a plain bar drawn by scaleX. (An SVG path
					// was tried first: with vector-effect non-scaling-stroke,
					// Chrome computes dash patterns in device units while
					// getTotalLength reports local units, so the dash-hidden
					// state rendered as visible dashes. A transform has no
					// such trap.)
					gsap.set(q('.j-threadline'), { scaleX: 0, transformOrigin: 'left center' });
					gsap.set(q('.j-serif'), { opacity: 0, y: 18 });
					gsap.set(q('.j-finalline'), { opacity: 0, y: 12 });
					gsap.set(q('.j-hl'), { opacity: 0 });

					const tl = gsap.timeline({
						defaults: { ease: 'none' },
						scrollTrigger: {
							trigger: root,
							start: 'top top',
							end: isDesktop ? '+=520%' : '+=400%',
							pin: true,
							scrub: 0.6,
							anticipatePin: 1,
						},
					});

					/* ── Scene 1 · the ring (0.3 – 2.3) ─────────────────────── */
					tl.to(q('.j-dim'), { opacity: 0.1, duration: 2 }, 0.3);
					tl.to(q('.j-land'), { y: -56, opacity: 0, duration: 0.9 }, 0.3);
					tl.to(q('.j-undercard'), { opacity: 0, duration: 0.5 }, 0.3);
					tl.to(stagecol, { x: xCenter, duration: 1.5 }, 0.5);
					tl.to(q('.j-halo-1'), { opacity: 0.75, scale: 1, duration: 0.3 }, 0.55);
					tl.to(q('.j-halo-1'), { opacity: 0, scale: 1.9, duration: 0.6 }, 0.85);
					tl.to(q('.j-halo-2'), { opacity: 0.75, scale: 1, duration: 0.3 }, 1.0);
					tl.to(q('.j-halo-2'), { opacity: 0, scale: 1.9, duration: 0.6 }, 1.3);
					tl.to(q('.j-state-ring'), { opacity: 0, duration: 0.4 }, 1.55);
					tl.to(q('.j-state-live'), { opacity: 1, duration: 0.4 }, 1.6);
					tl.to(bars, { scaleY: (i: number) => speaking(i), duration: 1.2, stagger: 0.03 }, 1.6);
					tl.to(q('[data-line="greeting"]'), { opacity: 1, y: 0, duration: 0.6 }, 1.7);

					/* ── Scene 2 · the conversation flows out (2.4 – 6.6) ───── */
					tl.to(stagecol, { x: xDock, duration: 0.8 }, 2.4);
					if (!isDesktop) {
						// Mobile: the stage shrinks and lifts so the callout slot
						// under it never has to overlap the card.
						tl.to(stagecol, { scale: 0.8, y: -120, duration: 0.8 }, 2.4);
					}
					tl.to(q('[data-line="ask"]'), { opacity: 1, y: 0, duration: 0.5 }, 2.7);

					// A line lifts out of the phone and lands as a callout.
					const lift = (n: number, at: number) => {
						const liftEl = q(`[data-lift="${n}"]`);
						const callout = q(`[data-callout="${n}"]`);
						// Mobile callouts share one slot under the card, so the
						// previous callout hands the slot over instead of stacking.
						if (!isDesktop && n > 1) {
							tl.to(q(`[data-callout="${n - 1}"]`), { opacity: 0, y: -10, duration: 0.35 }, at + 0.35);
						}
						tl.to(liftEl, { opacity: 1, y: 0, duration: 0.25 }, at);
						tl.to(liftEl, isDesktop ? { x: liftTravel, duration: 0.6 } : { y: -10, duration: 0.6 }, at + 0.1);
						tl.to(liftEl, { opacity: 0, duration: 0.25 }, at + 0.6);
						tl.to(callout, { opacity: 1, y: 0, duration: 0.5 }, at + 0.55);
						tl.to(q(`[data-callout="${n}"] .j-callout-rule`), { scaleX: 1, duration: 0.5 }, at + 0.55);
					};

					lift(1, 3.0);
					tl.to(q('[data-line="slots"]'), { opacity: 1, y: 0, duration: 0.5 }, 3.9);
					tl.to(q('[data-line="thursday"]'), { opacity: 1, y: 0, duration: 0.5 }, 4.5);
					lift(2, 4.8);
					tl.to(q('[data-line="booked"]'), { opacity: 1, y: 0, duration: 0.5 }, 5.6);
					lift(3, 5.9);

					/* ── Scene 3 · the interruption (6.9 – 8.8) ─────────────── */
					tl.to(q('.j-callout'), { opacity: 0, y: -14, duration: 0.5 }, 6.9);
					tl.to(stagecol, { x: xCenter, duration: 0.8 }, 7.0);
					tl.to(q('.j-lines-main'), { opacity: 0, duration: 0.4 }, 7.3);
					tl.to(q('.j-lines-cut'), { opacity: 1, duration: 0.4 }, 7.45);
					tl.to(bars, { scaleY: 0.07, duration: 0.5, stagger: 0.01 }, 7.4);
					tl.to(q('.j-cutline'), { textDecorationColor: 'rgba(28, 20, 8, 1)', duration: 0.5 }, 7.8);
					tl.to(q('.j-serif'), { opacity: 1, y: 0, duration: 0.7 }, 8.0);
					tl.to(q('.j-cut-chip'), { opacity: 1, scale: 1, duration: 0.35 }, 8.25);

					/* ── Scene 4 · the booking docks (8.9 – 11.8) ───────────── */
					tl.to(q('.j-serif'), { opacity: 0, y: -12, duration: 0.45 }, 8.9);
					tl.to(q('.j-lines-cut'), { opacity: 0, duration: 0.4 }, 9.0);
					tl.to(q('.j-lines-main'), { opacity: 1, duration: 0.4 }, 9.1);
					tl.to(bars, { scaleY: (i: number) => speaking(i), duration: 0.6, stagger: 0.02 }, 9.1);
					tl.to(stagecol, { x: xDock, duration: 0.8 }, 9.2);
					tl.to(q('.j-hl'), { opacity: 1, duration: 0.5 }, 9.5);
					tl.to(q('.j-threadline'), { scaleX: 1, duration: 1.0 }, 9.6);
					tl.to(q('.j-crm'), { opacity: 1, x: 0, y: 0, duration: 0.6 }, 10.1);
					if (!isDesktop) {
						// Mobile: the record docks as a sheet over a quieted stage.
						tl.to(stagecol, { opacity: 0.35, duration: 0.6 }, 10.1);
					}
					tl.to(q('.j-field'), { opacity: 1, scale: 1, y: 0, duration: 0.4, stagger: 0.35 }, 10.4);
					tl.to(q('.j-finalline'), { opacity: 1, y: 0, duration: 0.5 }, 11.3);
					tl.to({}, { duration: 0.4 }, 11.8);
				},
			);
		}, root);

		return () => {
			root.classList.remove('journey--static');
			ctx.revert();
		};
	}, []);

	return (
		<section ref={rootRef} className="journey" aria-label="One call, start to finish">
			<div className="j-pin">
				<div className="j-dim" aria-hidden="true" />
				<div className="j-inner">
					{/* Scene 0 · land */}
					<div className="j-land">
						<p className="j-eyebrow">The 9pm call · a clinic line</p>
						<h1 className="j-h1">
							It picks up<span style={{ color: 'var(--theme-accent)' }}>.</span>
						</h1>
						<p className="j-one-line">Wavia answers in Urdu, English, Arabic and Bahasa Melayu.</p>
						<p className="j-cue" aria-hidden="true">
							Scroll
							<span className="j-cue-thread" />
						</p>
					</div>

					{/* The stage: the call itself, present in every scene. */}
					<div className="j-stagecol">
						<CallStage />
						<div className="j-undercard">
							<p className="j-langnames">
								<span style={{ fontFamily: 'var(--font-urdu)' }}>اردو</span>
								{' · English · '}
								<span style={{ fontFamily: 'var(--font-arabic)' }}>العربية</span>
								{' · Bahasa Melayu'}
							</p>
							<p className="j-honest">Scripted demo · transcript, no audio yet</p>
						</div>
					</div>

					{/* Scene 2 · the lines, out of the phone */}
					<div className="j-lift" data-lift="1" aria-hidden="true">
						<span>wavia</span>
						<p className="urdu" lang="ur" dir="rtl">
							السلام علیکم، یہ کلینک ہے۔ میں آپ کی کیا مدد کر سکتا ہوں؟
						</p>
					</div>
					<div className="j-lift" data-lift="2" aria-hidden="true">
						<span>caller</span>
						<p>Thursday, ten.</p>
					</div>
					<div className="j-lift" data-lift="3" aria-hidden="true">
						<span>wavia</span>
						<p>Booked. I have sent you a confirmation message.</p>
					</div>

					{CALLOUTS.map((c, i) => (
						<div key={c.tick} className="j-callout" data-callout={i + 1}>
							<span className="j-callout-tick">{c.tick}</span>
							<span className="j-callout-rule" aria-hidden="true" />
							<p>{c.text}</p>
							{c.sub && <span className="j-callout-sub">{c.sub}</span>}
						</div>
					))}

					{/* Scene 3 · the one human line */}
					<p className="j-serif">It stops talking the moment your caller starts.</p>

					{/* Scene 4 · the thread to the record */}
					<div className="j-threadline" aria-hidden="true" />

					<div className="j-crm">
						<div className="j-crm-head">
							<span>CRM record</span>
							<span className="j-crm-dot" aria-hidden="true" />
						</div>
						{CRM_FIELDS.map((f) => (
							<div key={f.k} className="j-field">
								<span className="j-field-k">{f.k}</span>
								<span className="j-field-v">{f.v}</span>
							</div>
						))}
						<p className="j-crm-foot">Written from the call itself</p>
					</div>

					<p className="j-finalline">Booked — and written where your team works.</p>
				</div>
			</div>
		</section>
	);
}
