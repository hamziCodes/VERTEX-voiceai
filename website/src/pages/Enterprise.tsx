import { Headphones, Lock, PhoneCall, Server, ShieldCheck } from 'lucide-react';
import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, H3, Lead, Section } from '@/components/ui';

const CARDS = [
  {
    icon: ShieldCheck,
    title: 'Bespoke B2B Custom Builds',
    body: 'Vertex Studio engineers work directly with your team to design, build, and deploy custom end-to-end voice workflows tailored to your specific business operations.'
  },
  {
    icon: Lock,
    title: 'Healthcare & Finance Compliant',
    body: 'HIPAA, SOC 2, and GDPR compliant architectures. Zero audio training retention, end-to-end encryption, and strict data fencing.'
  },
  {
    icon: Server,
    title: 'Dedicated VPC & Self-Hosted Option',
    body: 'Deploy dedicated containerized instances inside your private AWS/GCP VPC or sovereign on-premise infrastructure.'
  },
  {
    icon: PhoneCall,
    title: 'SIP Trunking & PBX Integration',
    body: 'Plugs seamlessly into existing call center setups, Cisco/Avaya PBX, Twilio Elastic SIP, or telecom carriers without rip-and-replace.'
  },
  {
    icon: Headphones,
    title: 'Dedicated Solutions Architect & SLA',
    body: 'Named lead engineer, custom toolchain integrations, guaranteed latency uptime SLAs, and 24/7 critical response escalation.'
  }
];

export default function Enterprise() {
  return (
    <>
			<section data-ev-id="ev_aadbc40b97" className="hero relative overflow-hidden">
				<div
					className="hero-glow"
					style={{
						background: 'radial-gradient(circle, rgba(198,161,91,var(--theme-glow-alpha)) 0%, transparent 65%)'
					}}
				/>
				<Container className="relative z-10 pb-20 pt-24 lg:pb-32 lg:pt-32">
					<div data-ev-id="ev_5c745d3827" className="flex max-w-3xl flex-col gap-6">
						<motion.div data-ev-id="ev_22b8d5e937" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Wavia Shield — Custom B2B & Enterprise</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_b90c2ce7a0" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								Built for the calls you
								<br data-ev-id="ev_9b677f5e25" />
								<GradientText>can’t get wrong.</GradientText>
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_a7b3c4fd6c" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>
								B2B bespoke custom engineering and high-compliance voice infrastructure. We use Wavia’s core intelligence engine to craft custom conversational solutions that integrate directly into your proprietary enterprise systems.
							</Lead>
						</motion.div>
						<motion.div data-ev-id="ev_7306418059" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3 }}>
							<BtnLink to="/contact">Request Custom Build / Consultation →</BtnLink>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section>
				<div data-ev-id="ev_44e1296c7c" className="flex flex-col gap-6 lg:flex-row lg:flex-wrap">
					{CARDS.map((c, i) =>
          <Reveal key={c.title} delay={i * 0.1} className="flex-1 lg:basis-[calc(50%-12px)]">
							<GlassCard className="flex h-full items-start gap-5">
								<div data-ev-id="ev_ef156169b5"
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
              style={{ background: 'var(--theme-shield-soft)', color: 'var(--theme-shield)' }}>

									<c.icon size={22} />
								</div>
								<div data-ev-id="ev_8d7e8534f7">
									<H3>{c.title}</H3>
									<p data-ev-id="ev_14c22fc891" className="mt-2 text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
										{c.body}
									</p>
								</div>
							</GlassCard>
						</Reveal>
          )}
				</div>
			</Section>

			<Section>
				<Reveal>
					<GlassCard className="flex flex-col items-center gap-8 text-center lg:flex-row lg:justify-between lg:text-left">
						<H2 className="max-w-lg">Let’s scope it together.</H2>
						<BtnLink to="/contact">Talk to Our Team →</BtnLink>
					</GlassCard>
				</Reveal>
			</Section>
		</>
  );
}
