import { motion } from 'motion/react';
import { Reveal } from '@/components/Reveal';
import { BtnLink, Container, Eyebrow, GlassCard, GradientText, H1, H2, H3, Lead, Section } from '@/components/ui';

const SNIPPET = `import { WaviaCore } from '@wavia/core';

const client = new WaviaCore({ apiKey: process.env.WAVIA_API_KEY });

const session = await client.sessions.create({
  voice: 'aria',
  language: 'en',
  interruptible: true,
  onTranscript: (chunk) => console.log(chunk.text),
});

await session.connect();`;

const CAPABILITIES = [
{ title: 'Streaming sessions', body: 'Bidirectional audio over WebSocket or WebRTC with server-side barge-in.' },
{ title: 'Tool calls', body: 'Register typed functions the assistant can invoke mid-call — booking, lookups, transfers.' },
{ title: 'Per-call telemetry', body: 'Latency, interruption counts, and transcripts streamed to your observability stack.' },
{ title: 'Webhooks', body: 'Signed events for call start, transfer, and completion.' }];


export default function ForDevelopers() {
  return (
    <>
			<section data-ev-id="ev_ef10bf174e" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-20 pt-24 lg:pb-32 lg:pt-32">
					<div data-ev-id="ev_9ef5df3f55" className="flex max-w-3xl flex-col gap-6">
						<motion.div data-ev-id="ev_7ce3caf399" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Wavia Core — The engine underneath</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_ee57417e8f" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								Voice AI with <GradientText>engineering authority.</GradientText>
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_b11af01416" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>Full SDK access for low-latency full-duplex audio, client barge-in, and custom tool calling.</Lead>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section>
				<div data-ev-id="ev_10050eac4f" className="flex flex-col items-start gap-16 lg:flex-row">
					<Reveal className="flex-1">
						<H2>Start a call in nine lines.</H2>
						<p data-ev-id="ev_8a909233bc" className="mt-4 text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
							One SDK, one session object. Interruption handling is on by default.
						</p>
					</Reveal>
					<Reveal delay={0.1} className="flex-1">
						<pre data-ev-id="ev_e7beed6c76"
            className="overflow-x-auto rounded-xl p-8"
            style={{
              background: 'var(--theme-surface)',
              border: '1px solid var(--theme-border)',
              boxShadow: 'none'
            }}>

							<code data-ev-id="ev_a3841f4a31" className="font-mono text-sm" style={{ color: 'var(--theme-fg-muted)' }}>
								{SNIPPET}
							</code>
						</pre>
					</Reveal>
				</div>
			</Section>

			<Section>
				<Reveal className="mb-12">
					<H2>What’s in the toolkit.</H2>
				</Reveal>
				<div data-ev-id="ev_28a5e2a748" className="flex flex-col gap-6 lg:flex-row">
					{CAPABILITIES.map((c, i) =>
          <Reveal key={c.title} delay={i * 0.1} className="flex-1">
							<GlassCard className="flex h-full flex-col gap-4">
								<H3>{c.title}</H3>
								<p data-ev-id="ev_3032876c2f" className="text-base" style={{ color: 'var(--theme-fg-muted)', lineHeight: 1.7 }}>
									{c.body}
								</p>
							</GlassCard>
						</Reveal>
          )}
				</div>
			</Section>

			<Section>
				<Reveal>
					<GlassCard className="flex flex-col items-center gap-8 text-center lg:flex-row lg:justify-between lg:text-left">
						<H2 className="max-w-lg">Get an API key and make your first call.</H2>
						<div data-ev-id="ev_094c4c787a" className="flex flex-col gap-4 sm:flex-row">
							<BtnLink to="/login">Get an API key →</BtnLink>
							<BtnLink to="/contact" variant="outline">Talk to an engineer</BtnLink>
						</div>
					</GlassCard>
				</Reveal>
			</Section>
		</>
  );
}
