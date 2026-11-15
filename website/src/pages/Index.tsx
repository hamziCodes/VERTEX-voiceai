import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Link } from 'react-router';
import {
  CalendarCheck,
  KeyRound,
  Languages,
  Lock,
  MessageCircle,
  MicOff,
  Minus,
  Phone,
  Plus,
  ShieldCheck,
  Zap } from
'lucide-react';
import { Waveform, type WaveState } from '@/components/Waveform';
import { InteractiveDemo } from '@/components/InteractiveDemo';
import { Counter } from '@/components/Counter';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, H3, Lead, Section } from '@/components/ui';

const CYCLE: {state: WaveState;ms: number;}[] = [
{ state: 'idle', ms: 2500 },
{ state: 'listening', ms: 2500 },
{ state: 'thinking', ms: 800 },
{ state: 'speaking', ms: 2200 }];


const STATS = [
{ value: '<400ms', label: 'Response time', hint: 'Full-duplex latency' },
{ value: '99.9%', label: 'Uptime guarantee', hint: 'Auto-failover architecture' },
{ value: '4', label: 'Languages supported', hint: 'Natural human cadence' },
{ value: '0', label: 'Data sold or shared', hint: 'Zero model training' }];


const PATHS = [
  {
    subBrand: 'Wavia Studio',
    tagline: 'Build it like a slide, not a script.',
    accent: 'var(--theme-verify)',
    badge: 'NO-CODE DASHBOARD',
    title: 'For Business Owners',
    body: 'Set up an autonomous conversational phone assistant in minutes. Visually design conversation flows, pick voice tone, and connect your phone number.',
    cta: 'Launch Wavia Studio →',
    to: '/get-started'
  },
  {
    subBrand: 'Wavia Core',
    tagline: 'The engine underneath.',
    accent: 'var(--theme-accent)',
    badge: 'DEVELOPER ENGINE',
    title: 'For Engineers & Builders',
    body: 'Full SDK access to our sub-400ms unified full-duplex engine. WebSocket and WebRTC streaming, client barge-in, typed tool calls, and live observability.',
    cta: 'Explore Wavia Core SDK →',
    to: '/for-developers'
  },
  {
    subBrand: 'Wavia Shield',
    tagline: "Built for the calls you can't get wrong.",
    accent: 'var(--theme-shield)',
    badge: 'B2B CUSTOM BUILDS',
    title: 'For Enterprises & High Compliance',
    body: 'Custom B2B solutions engineered by Vertex Studio. Dedicated VPC & on-prem hosting, HIPAA/GDPR compliance, SIP trunking, and tailored agent integrations.',
    cta: 'Consult Wavia Shield Team →',
    to: '/enterprise'
  }
];


const BENEFITS = [
{
  icon: MessageCircle,
  title: 'Real conversations',
  body: 'No waiting for scripts. Talk over it, change topics — it keeps up.'
},
{
  icon: Zap,
  title: 'Always on',
  body: 'Auto-failover keeps calls going even if something hiccups.'
},
{
  icon: Languages,
  title: 'Natural multilingual',
  body: 'English, Urdu, Arabic, Malay — natural pacing, not robotic.'
},
{
  icon: CalendarCheck,
  title: 'Takes action',
  body: 'Books appointments, checks calendars, syncs to your systems.'
}];


const TRUST_ITEMS = [
{
  icon: MicOff,
  title: 'No-Recording Ephemeral Mode',
  body: 'Raw audio streams and transcripts are processed in memory and discarded instantly when the call disconnects.'
},
{
  icon: Lock,
  title: 'Internal Data Fencing',
  body: 'Customer and patient information stays strictly within your isolated perimeter — zero external data leakage.'
},
{
  icon: ShieldCheck,
  title: 'Zero Model Training',
  body: 'Your business phone calls, workflows, and prompts are never used to train external or foundation AI models.'
},
{
  icon: KeyRound,
  title: 'Cryptographically Verified',
  body: 'Enterprise-grade TLS 1.3 encryption and signed cryptographic payloads for all webhooks and tool executions.'
}];


const FAQS = [
{ q: 'Will it sound robotic?', a: 'No — sub-second responses, natural conversation flow, not a phone menu.' },
{ q: 'How long to set up?', a: 'About 5 minutes with our guided setup. No coding required.' },
{ q: 'Keep my number?', a: 'Yes. Connect existing or get a new one in clicks.' },
{ q: 'Developer control?', a: 'Full SDK with streaming, tool calls, and real-time telemetry.' },
{ q: 'HIPAA/PCI safe?', a: 'Yes — special mode keeps sensitive data internal. Contact us.' },
{ q: 'Pricing?', a: 'Pay-as-you-go from $29/mo. Enterprise custom quotes available.' }];


function FaqItem({ q, a }: {q: string;a: string;}) {
  const [open, setOpen] = useState(false);

  return (
    <div data-ev-id="ev_d9a7fdeeee" style={{ borderBottom: '1px solid var(--theme-border)' }}>
			<button data-ev-id="ev_127f9817cc"
      type="button"
      onClick={() => setOpen((v) => !v)}
      aria-expanded={open}
      className="flex w-full items-center justify-between gap-6 py-6 text-left">

				<span data-ev-id="ev_55cc238246" className="font-display text-lg font-semibold" style={{ color: 'var(--theme-fg)' }}>
					{q}
				</span>
				<span data-ev-id="ev_91a096397b" style={{ color: 'var(--theme-accent)' }}>
					{open ? <Minus size={20} aria-hidden /> : <Plus size={20} aria-hidden />}
				</span>
			</button>
			<motion.div data-ev-id="ev_c36803f330"
      initial={false}
      animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="overflow-hidden">

				<p data-ev-id="ev_1839aad2f5" className="pb-6 text-base" style={{ color: 'var(--theme-fg-muted)' }}>{a}</p>
			</motion.div>
		</div>);

}

export default function Index() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = window.setTimeout(() => setStep((v) => (v + 1) % CYCLE.length), CYCLE[step].ms);
    return () => window.clearTimeout(t);
  }, [step]);

  return (
    <>
			{/* Hero */}
			<section
				className="hero-glow relative overflow-hidden"
				style={{ background: 'var(--theme-bg)' }}
			>
				<Container className="relative z-10 pb-24 pt-20 lg:pb-32 lg:pt-28">
					<div data-ev-id="ev_4617f1789a" className="mx-auto flex max-w-4xl flex-col items-center gap-6 text-center">
						<motion.div
							initial={{ opacity: 0, y: 16 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, ease: 'easeOut' }}
						>
							<Eyebrow>Always listening. Never robotic.</Eyebrow>
						</motion.div>

						<motion.div
							initial={{ opacity: 0, y: 16 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, ease: 'easeOut', delay: 0.1 }}
						>
							<H1>
								Meet the voice AI that
								<br />
								<GradientText>actually lets you talk.</GradientText>
							</H1>
						</motion.div>

						<motion.div
							initial={{ opacity: 0, y: 16 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
						>
							<Lead className="mx-auto max-w-2xl">
								Interrupt it, ask something different, change your mind mid-sentence — it keeps up, just like a real person would.
							</Lead>
						</motion.div>

						<motion.div
							initial={{ opacity: 0, y: 16 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, ease: 'easeOut', delay: 0.3 }}
							className="flex flex-col gap-4 sm:flex-row"
						>
							<BtnLink to="/get-started">Get Started Free →</BtnLink>
							<BtnLink to="/how-it-works" variant="outline">See How It Works</BtnLink>
						</motion.div>

						<motion.div
							initial={{ opacity: 0, scale: 0.95 }}
							animate={{ opacity: 1, scale: 1 }}
							transition={{ duration: 0.6, ease: 'easeOut', delay: 0.4 }}
							className="mt-6 flex flex-col items-center gap-4 rounded-xl p-6 lg:p-8 border border-[var(--theme-border)] bg-[var(--theme-surface)]"
						>
							<div
								className="flex items-center justify-center rounded-lg p-5 border border-[var(--theme-border)] bg-[var(--theme-surface-2)]"
							>
								<Waveform state={CYCLE[step].state} height={60} barWidth={8} gap={8} />
							</div>
							<p className="text-sm font-medium" style={{ color: 'var(--theme-fg-muted)' }}>
								{CYCLE[step].state === 'idle' && 'Waiting for a caller'}
								{CYCLE[step].state === 'listening' && 'Listening to the caller'}
								{CYCLE[step].state === 'thinking' && 'Working out the answer'}
								{CYCLE[step].state === 'speaking' && 'Speaking back — interruptible'}
							</p>
						</motion.div>
					</div>
				</Container>
			</section>

			{/* Stats */}
			<Section className="!py-8 lg:!py-12">
				<div data-ev-id="ev_c3a4a89f5d" className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface)] p-6 lg:p-8">
					<div className="grid grid-cols-2 gap-6 lg:grid-cols-4 lg:divide-x lg:divide-[var(--theme-border)]">
						{STATS.map((s, i) =>
							<Reveal key={s.label} delay={i * 0.08} className={i > 0 ? "lg:pl-8" : ""}>
								<div data-ev-id="ev_39b5652cb1" className="flex flex-col items-center text-center">
									<span data-ev-id="ev_ae2dcc9b33"
										className="font-display text-4xl font-bold lg:text-5xl"
										style={{ color: 'var(--theme-accent)' }}>
										<Counter value={s.value} />
									</span>
									<span data-ev-id="ev_eb1175f050" className="mt-2 text-sm font-semibold" style={{ color: 'var(--theme-fg)' }}>
										{s.label}
									</span>
									<span className="mt-0.5 text-xs font-mono" style={{ color: 'var(--theme-fg-muted)' }}>
										{s.hint}
									</span>
								</div>
							</Reveal>
						)}
					</div>
				</div>
			</Section>

			{/* Demo */}
			<Section>
				<Reveal className="mb-12 text-center">
					<H2>Try interrupting it yourself.</H2>
					<Lead className="mx-auto mt-4 max-w-xl">No sign-up needed. Click the button and talk over it.</Lead>
				</Reveal>
				<InteractiveDemo />
			</Section>

			{/* Paths */}
			<Section>
				<Reveal className="mb-12 text-center">
					<Eyebrow>The Wavia Ecosystem</Eyebrow>
					<H2 className="mt-4">Three sub-products. One unbroken engine.</H2>
					<Lead className="mx-auto mt-4 max-w-xl">Whether you’re building visually, integrating into code, or deploying high-compliance enterprise infrastructure.</Lead>
				</Reveal>
				<div data-ev-id="ev_6c24145642" className="flex flex-col gap-6 lg:flex-row">
					{PATHS.map((p, i) =>
          <Reveal key={p.title} delay={i * 0.1} className="flex-1">
							<GlassCard className="flex h-full flex-col justify-between gap-5 relative overflow-hidden group">
								<div className="flex flex-col gap-3">
									<div className="flex items-center justify-between gap-2">
										<span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-full border" style={{ borderColor: p.accent, color: p.accent }}>
											{p.badge}
										</span>
										<span className="text-xs font-mono text-[var(--theme-fg-muted)]">
											{p.subBrand}
										</span>
									</div>
									<div>
										<H3 className="text-xl font-bold">{p.subBrand}</H3>
										<p className="text-xs italic font-medium mt-0.5" style={{ color: p.accent }}>
											“{p.tagline}”
										</p>
									</div>
									<p data-ev-id="ev_88ed25630f" className="text-sm mt-1" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
										{p.body}
									</p>
								</div>
								<Link data-ev-id="ev_46452c0a0d"
              to={p.to}
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold transition-all duration-200 group-hover:translate-x-1"
              style={{ color: p.accent }}>
									{p.cta}
								</Link>
							</GlassCard>
						</Reveal>
          )}
				</div>
			</Section>

			{/* Benefits */}
			<Section>
				<div data-ev-id="ev_224dc73201" className="flex flex-col items-center gap-16 lg:flex-row lg:items-start lg:gap-24">
					<Reveal className="flex-1 lg:sticky lg:top-32">
						<H2>What it’s actually like.</H2>
						<Lead className="mt-4 max-w-md">No compromises on conversation quality.</Lead>
					</Reveal>
					<div data-ev-id="ev_94c027656a" className="flex flex-1 flex-col gap-6">
						{BENEFITS.map((b, i) =>
            <Reveal key={b.title} delay={i * 0.1}>
								<GlassCard className="flex items-start gap-5">
									<div data-ev-id="ev_d1256030ef"
										className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-[var(--theme-border)] bg-[var(--theme-surface-2)]"
										style={{ color: 'var(--theme-accent)' }}>
										<b.icon size={22} strokeWidth={2} />
									</div>
									<div data-ev-id="ev_0ec462eb9b">
										<H3>{b.title}</H3>
										<p data-ev-id="ev_960ddddc59" className="mt-2 text-base" style={{ color: 'var(--theme-fg-muted)' }}>
											{b.body}
										</p>
									</div>
								</GlassCard>
							</Reveal>
            )}
					</div>
				</div>
			</Section>

			{/* Phone */}
			<Section>
				<Reveal>
					<div
						className="flex flex-col items-center gap-6 rounded-xl p-8 text-center lg:p-14 border border-[var(--theme-border)] bg-[var(--theme-surface)]"
					>
						<div
							className="flex h-14 w-14 items-center justify-center rounded-lg border border-[var(--theme-border)] bg-[var(--theme-surface-2)] text-[var(--theme-accent)]"
						>
							<Phone size={26} />
						</div>
						<H2>Works with your number.</H2>
						<Lead className="max-w-2xl">
							Keep your current number or get a new one. If your provider has an outage, calls auto-route to a backup. Your business stays reachable.
						</Lead>
					</div>
				</Reveal>
			</Section>

			{/* Trust */}
			<Section>
				<div data-ev-id="ev_5dd17fb311" className="flex flex-col gap-12 lg:gap-16">
					<Reveal className="mx-auto flex max-w-2xl flex-col items-center text-center">
						<div data-ev-id="ev_84be19d36b"
							className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg border border-[var(--theme-border)] bg-[var(--theme-surface-2)]"
							style={{ color: 'var(--theme-verify)' }}>
							<ShieldCheck size={28} />
						</div>
						<Eyebrow>Enterprise Trust & Privacy</Eyebrow>
						<H2 className="mt-3">Private. Period.</H2>
						<Lead className="mt-3">
							Engineered for zero audio leakage, airtight compliance, and sovereign data custody.
						</Lead>
					</Reveal>
					<div className="grid gap-6 sm:grid-cols-2">
						{TRUST_ITEMS.map((t, i) =>
							<Reveal key={t.title} delay={i * 0.08}>
								<GlassCard className="flex h-full flex-col gap-3">
									<div
										className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--theme-border)] bg-[var(--theme-surface-2)]"
										style={{ color: 'var(--theme-accent)' }}>
										<t.icon size={18} strokeWidth={2} />
									</div>
									<H3 className="text-lg font-bold">{t.title}</H3>
									<p className="text-sm leading-relaxed" style={{ color: 'var(--theme-fg-muted)' }}>
										{t.body}
									</p>
								</GlassCard>
							</Reveal>
						)}
					</div>
				</div>
			</Section>

			{/* FAQ */}
			<Section>
				<div data-ev-id="ev_e871e0008b" className="mx-auto max-w-3xl">
					<Reveal className="mb-12 text-center">
						<H2>Questions.</H2>
					</Reveal>
					<div data-ev-id="ev_6653921a02">
						{FAQS.map((f, i) =>
							<Reveal key={f.q} delay={i * 0.06}>
								<FaqItem q={f.q} a={f.a} />
							</Reveal>
						)}
					</div>
				</div>
			</Section>

			{/* CTA */}
			<Section>
				<Reveal>
					<div
						className="flex flex-col items-center gap-8 rounded-xl p-10 text-center lg:p-16 border border-[var(--theme-border)] bg-[var(--theme-surface)]"
					>
						<h2
							className="font-display text-[1.75rem] font-bold text-[var(--theme-fg)] lg:text-[2.75rem] tracking-tight"
							style={{ lineHeight: 1.15 }}
						>
							Ready for a voice assistant that listens?
						</h2>
						<Lead className="max-w-xl">
							Start free in five minutes. No setup fees, no contracts, no complex onboarding.
						</Lead>
						<div data-ev-id="ev_859dfa93de" className="flex flex-col gap-4 sm:flex-row">
							<BtnLink to="/get-started">Get Started Free →</BtnLink>
							<BtnLink to="/contact" variant="outline">Talk to Our Team</BtnLink>
						</div>
					</div>
				</Reveal>
			</Section>
		</>);

}
