import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { Container, Eyebrow, GradientText, H1, H3, Lead, Section } from '@/components/ui';

const SECTIONS = [
{ title: 'Using the service', body: 'You may use Wavia products (Wavia Studio, Wavia Core, Wavia Shield) to answer calls for a business you own or are authorised to represent. You are responsible for what your assistant says.' },
{ title: 'Billing', body: 'Plans are billed monthly, plus usage. Cancel any time and keep access until the period ends.' },
{ title: 'Availability', body: 'We run redundant systems and auto-failover, but don’t guarantee uninterrupted service except under enterprise agreements.' },
{ title: 'Changes', body: 'If we change these terms meaningfully, we’ll email you before the change takes effect.' }];


export default function Terms() {
  return (
    <>
			<section data-ev-id="ev_89caf7c50d" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-16 pt-24 lg:pb-24 lg:pt-32">
					<div data-ev-id="ev_6ae59d9761" className="mx-auto flex max-w-3xl flex-col gap-6">
						<motion.div data-ev-id="ev_6916f2b6b7" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Legal</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_ca90f17418" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								<GradientText>Terms</GradientText> of Service
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_bf56275231" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>The short version of what you agree to when you use Wavia by Wavia Labs.</Lead>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section>
				<div data-ev-id="ev_e49847ca04" className="mx-auto max-w-3xl">
					{SECTIONS.map((s, i) =>
          <Reveal key={s.title} delay={i * 0.08}>
							<div data-ev-id="ev_c0727fb903"
            className="flex flex-col gap-3 py-8"
            style={{ borderBottom: i < SECTIONS.length - 1 ? '1px solid var(--theme-border)' : 'none' }}>

								<H3>{s.title}</H3>
								<p data-ev-id="ev_bf458e0032" className="text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
									{s.body}
								</p>
							</div>
						</Reveal>
          )}
				</div>
			</Section>
		</>);

}
