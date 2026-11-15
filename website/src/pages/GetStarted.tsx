import { CalendarClock, Mic2, Phone, UserRound } from 'lucide-react';
import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, H3, Lead, Section } from '@/components/ui';

const STEPS = [
{
  n: '1',
  icon: UserRound,
  title: 'Name & personality',
  body: 'Type a few sentences about your business and how you want it to sound.'
},
{
  n: '2',
  icon: Mic2,
  title: 'Choose a voice',
  body: 'Listen to a handful of voices and pick the one that fits.'
},
{
  n: '3',
  icon: CalendarClock,
  title: 'Set your hours',
  body: 'When to answer, when to take a message, when to transfer.'
},
{
  n: '4',
  icon: Phone,
  title: 'Connect your number',
  body: 'Keep your current number or get a new one. First call happens right after.'
}];


export default function GetStarted() {
  return (
    <>
			<section data-ev-id="ev_e814a03334" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-8 pt-20 lg:pb-12 lg:pt-28">
					<div data-ev-id="ev_f637b365a4" className="mx-auto flex max-w-3xl flex-col items-center gap-6 text-center">
						<motion.div data-ev-id="ev_ca679c3cb6" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Wavia Studio — Build it like a slide, not a script</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_ee6883e422" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								Fill out a form,
								<br data-ev-id="ev_24305587de" />
								<GradientText>not a codebase.</GradientText>
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_d4fc1b43a4" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>Four steps, about five minutes.</Lead>
						</motion.div>
						<motion.div data-ev-id="ev_a8a445d656"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col gap-4 sm:flex-row">

							<BtnLink to="/login">Create your account →</BtnLink>
							<BtnLink to="/contact" variant="outline">Get help setting up</BtnLink>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section className="!pt-6 lg:!pt-10">
				<div data-ev-id="ev_bfae1eb831" className="relative mx-auto max-w-2xl">
					{/* Vertical line */}
					<div data-ev-id="ev_8fa3cc4fd8"
          className="absolute left-7 top-0 hidden h-full w-px lg:block"
          style={{ background: 'var(--theme-border)' }} />

					{STEPS.map((s, i) =>
          <Reveal key={s.n} delay={i * 0.1}>
							<div data-ev-id="ev_19a0c84ef6" className="flex gap-8 pb-12">
								<div data-ev-id="ev_3c40b36c04"
              className="relative z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-xl"
              style={{
                background: 'var(--theme-surface-2)',
                border: '1px solid var(--theme-border)',
                color: 'var(--theme-accent)'
              }}>

									<s.icon size={24} />
								</div>
								<div data-ev-id="ev_f04a4931df" className="flex flex-col gap-2 pt-2">
									<H3>{s.title}</H3>
									<p data-ev-id="ev_d829169536" className="text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
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
						<H2 className="max-w-lg">Nothing to install. Nothing to configure.</H2>
						<BtnLink to="/login">Get Started Free →</BtnLink>
					</GlassCard>
				</Reveal>
			</Section>
		</>
  );
}
