import { Check } from 'lucide-react';
import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GradientText, H1, H3, Lead, Section } from '@/components/ui';

const PLANS = [
  {
    name: 'Wavia Studio',
    badge: 'NO-CODE DASHBOARD',
    price: '$29',
    suffix: '/mo + usage',
    for: 'Small businesses & teams',
    accentColor: 'var(--theme-verify)',
    features: ['One visual assistant', 'Keep your existing number', 'Visual prompt designer', 'Booking & calendar built in', 'Standard support'],
    cta: 'Get Started with Studio →',
    to: '/get-started',
    highlight: false
  },
  {
    name: 'Wavia Core',
    badge: 'DEVELOPER ENGINE',
    price: '$149',
    suffix: '/mo + usage',
    for: 'High-growth & developer apps',
    accentColor: 'var(--theme-accent)',
    features: ['Full SDK & WebRTC access', 'All 4 languages + custom voices', 'Streaming API, interruptible by default', 'Custom tool & function calls', 'Real-time telemetry', 'Priority support'],		cta: 'Start building →',
    to: '/for-developers',
    highlight: true
  },
  {
    name: 'Wavia Shield',
    badge: 'B2B CUSTOM BUILDS',
    price: 'Custom',
    suffix: 'talk to us',
    for: 'Enterprises & high compliance',
    accentColor: 'var(--theme-shield)',
    features: ['Bespoke B2B builds', 'Dedicated VPC or on-prem deployment', 'Data fencing & no-recording mode', 'Direct SIP trunking into legacy PBX', '24/7 designated solutions architect'],
    cta: 'Consult Shield Team →',
    to: '/contact',
    highlight: false
  }
];

export default function Pricing() {
  return (
    <>
			<section data-ev-id="ev_a41d2a28b8" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-16 pt-24 lg:pb-24 lg:pt-32">
					<div data-ev-id="ev_4008b5e13c" className="mx-auto flex max-w-3xl flex-col items-center gap-6 text-center">
						<motion.div data-ev-id="ev_64d12c73fd" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Pricing</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_7ece9c9574" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								Pay for what you <GradientText>use.</GradientText>
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_5ec3928555" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>Three lanes, one engine: Studio, Core and Shield.</Lead>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section>
				<div data-ev-id="ev_e4060fee13" className="flex flex-col gap-8 lg:flex-row">
					{PLANS.map((p, i) =>
          <Reveal key={p.name} delay={i * 0.1} className="flex-1">
							<motion.div data-ev-id="ev_642b3fdedb"
            className="flex h-full flex-col gap-6 rounded-xl p-8 lg:p-10 transition-shadow duration-300"
            style={{
              background: p.highlight ? 'var(--theme-surface-2)' : 'var(--theme-surface)',
              border: p.highlight ? '2px solid var(--theme-accent)' : '1px solid var(--theme-border)',
              boxShadow: 'none'
            }}
            whileHover={{
              y: -4,
              boxShadow: 'var(--theme-shadow)'
            }}
            transition={{ duration: 0.2 }}>

								<div data-ev-id="ev_0584eb40b6" className="flex flex-col gap-2">
									<div className="flex items-center justify-between">
										<span
											className="btn-tag"
											style={{
												borderColor: p.accentColor,
												color: p.accentColor
											}}>
											{p.badge}
										</span>
									</div>
									<H3 style={{ color: 'var(--theme-fg)' }}>{p.name}</H3>
									<p data-ev-id="ev_5e141e2b73" className="text-sm font-medium" style={{ color: 'var(--theme-fg-muted)' }}>
										{p.for}
									</p>
								</div>

								<div data-ev-id="ev_8a3456d1bb" className="flex items-baseline gap-2">
									<span data-ev-id="ev_a312a09ed8" className="font-display text-[3rem] font-bold" style={{ color: 'var(--theme-fg)' }}>
										{p.price}
									</span>
									<span data-ev-id="ev_412ec3b8c0" className="text-sm" style={{ color: 'var(--theme-fg-muted)' }}>
										{p.suffix}
									</span>
								</div>

								<ul data-ev-id="ev_47ffaa3fa6" className="flex flex-1 flex-col gap-3">
									{p.features.map((f) =>
                <li data-ev-id="ev_d30fd86db5" key={f} className="flex items-start gap-3 text-base" style={{ color: 'var(--theme-fg-muted)' }}>
											<Check
                    size={18}
                    className="mt-0.5 shrink-0"
                    style={{ color: p.accentColor }} />
											{f}
										</li>
                )}
								</ul>

								<BtnLink
									to={p.to}
									className="w-full justify-center"
									variant={p.highlight ? 'primary' : 'outline'}>
									{p.cta}
								</BtnLink>
							</motion.div>
						</Reveal>
          )}
				</div>
			</Section>
		</>
  );
}
