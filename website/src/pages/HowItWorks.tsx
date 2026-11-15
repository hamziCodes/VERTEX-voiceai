import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, H3, Lead, Section } from '@/components/ui';

const STEPS = [
{
  n: '01',
  title: 'Someone calls your business',
  body: 'The call comes in on your existing number. Wavia picks up straight away — no menus, no “press 1 for sales”.'
},
{
  n: '02',
  title: 'It listens while they talk',
  body: 'It follows the conversation as it happens, so the caller can ramble, correct themselves, or change the subject.'
},
{
  n: '03',
  title: 'It answers in under a second',
  body: 'No awkward pause. And if the caller talks over it, it stops and listens — exactly like a person would.'
},
{
  n: '04',
  title: 'It gets things done',
  body: 'Books the appointment, checks your calendar, takes a message, or hands the call to a person on your team.'
}];


export default function HowItWorks() {
  return (
    <>
			<section data-ev-id="ev_278e0df410" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-8 pt-20 lg:pb-12 lg:pt-28">
					<div data-ev-id="ev_7196964483" className="flex max-w-3xl flex-col gap-6">
						<motion.div data-ev-id="ev_0144b2ee11" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>How it works</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_fa3e4763c9" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								A real <GradientText>conversation</GradientText>,<br data-ev-id="ev_2e6db19826" />not a phone menu.
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_febc14b4b8" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>From the moment someone calls — in plain language, start to finish.</Lead>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section className="!pt-6 lg:!pt-10">
				<div data-ev-id="ev_ec09e45242" className="mx-auto max-w-3xl">
					{STEPS.map((s, i) =>
          <Reveal key={s.n} delay={i * 0.1}>
							<div data-ev-id="ev_2328734a17"
            className="flex gap-8 py-12"
            style={{ borderBottom: i < STEPS.length - 1 ? '1px solid var(--theme-border)' : 'none' }}>

								<div data-ev-id="ev_08c3dd383d"
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl font-display text-lg font-bold"
              style={{
                background: 'var(--theme-surface-2)',
                border: '1px solid var(--theme-border)',
                color: 'var(--theme-accent)'
              }}>

									{s.n}
								</div>
								<div data-ev-id="ev_afb97f5579" className="flex flex-col gap-3">
									<H3>{s.title}</H3>
									<p data-ev-id="ev_0ceab66b13" className="text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
										{s.body}
									</p>
								</div>
							</div>
						</Reveal>
          )}
				</div>
			</Section>

			<Section>
				<Reveal>
					<GlassCard className="flex flex-col items-center gap-8 text-center lg:flex-row lg:justify-between lg:text-left">
						<H2 className="max-w-lg">It takes about five minutes to set up.</H2>
						<BtnLink to="/get-started">Get Started Free →</BtnLink>
					</GlassCard>
				</Reveal>
			</Section>
		</>
  );
}
