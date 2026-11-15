import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, Lead, Section } from '@/components/ui';

export default function About() {
  return (
    <>
			<section data-ev-id="ev_99bcdb6b5d" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-8 pt-20 lg:pb-12 lg:pt-28">
					<div data-ev-id="ev_25f7121d63" className="flex max-w-3xl flex-col gap-6">
						<motion.div data-ev-id="ev_462527698a" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>About us</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_47cd19a0fb" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								We got tired of AI that
								<br data-ev-id="ev_59d589104f" />
								<GradientText>talks over people.</GradientText>
							</H1>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section className="!pt-6 lg:!pt-10">
				<div data-ev-id="ev_62cf64628f" className="mx-auto max-w-3xl">
					<Reveal>
						<div data-ev-id="ev_19c4a03046" className="flex flex-col gap-8">
							<Lead>
								Most voice AI products are three different companies’ tools duct-taped together. One turns voice to text, another writes the reply, a third reads it back. Every hand-off adds delay — and none are built to be interrupted.
							</Lead>
							<Lead>
								That’s why they feel slow, robotic, and why talking over them gets you nowhere.
							</Lead>
							<Lead>
								<strong>Wavia</strong> was built from the ground up to solve that. A single conversational engine with full-duplex listening and instant acoustic barge-in — it stops the moment you start talking.
							</Lead>
							<div className="grid sm:grid-cols-3 gap-6 pt-4">
								<div className="p-5 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface)]">
									<span className="btn-tag" style={{ color: 'var(--theme-accent)', borderColor: 'var(--theme-accent)' }}>DEVELOPER ENGINE</span>
									<p className="font-display font-semibold text-lg text-[var(--theme-fg)] mt-2">Wavia Core</p>
									<p className="text-sm text-[var(--theme-fg-muted)] mt-1">The engine underneath. Direct SDK access & low-level WebSocket streaming.</p>
								</div>
								<div className="p-5 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface)]">
									<span className="btn-tag" style={{ color: 'var(--theme-verify)', borderColor: 'var(--theme-verify)' }}>NO-CODE DASHBOARD</span>
									<p className="font-display font-semibold text-lg text-[var(--theme-fg)] mt-2">Wavia Studio</p>
									<p className="text-sm text-[var(--theme-fg-muted)] mt-1">Build it like a slide, not a script. Visual prompts, call routing, and phone setups.</p>
								</div>
								<div className="p-5 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface)]">
									<span className="btn-tag" style={{ color: 'var(--theme-shield)', borderColor: 'var(--theme-shield)' }}>B2B CUSTOM BUILDS</span>
									<p className="font-display font-semibold text-lg text-[var(--theme-fg)] mt-2">Wavia Shield</p>
									<p className="text-sm text-[var(--theme-fg-muted)] mt-1">Built for the calls you can’t get wrong. Bespoke custom builds & compliance.</p>
								</div>
							</div>
						</div>
					</Reveal>

					<Reveal className="mt-16">
						<blockquote data-ev-id="ev_00b5d0fa6c"
            className="rounded-xl p-8 lg:p-12 border border-[var(--theme-border)] bg-[var(--theme-surface)]">

							<p data-ev-id="ev_00dfc27f7c"
              className="font-display text-2xl font-semibold lg:text-3xl"
              style={{ color: 'var(--theme-fg)', lineHeight: 1.3 }}>

								“We think talking to a computer shouldn’t feel like talking to a computer.”
							</p>
						</blockquote>
					</Reveal>
				</div>
			</Section>

			<Section>
				<Reveal>
					<GlassCard className="flex flex-col items-center gap-8 text-center lg:flex-row lg:justify-between lg:text-left">
						<H2 className="max-w-lg">Hear the difference for yourself.</H2>
						<div data-ev-id="ev_39552af139" className="flex flex-col gap-4 sm:flex-row">
							<BtnLink to="/get-started">Get Started Free →</BtnLink>
							<BtnLink to="/contact" variant="outline">Talk to Our Team</BtnLink>
						</div>
					</GlassCard>
				</Reveal>
			</Section>
		</>);

}
