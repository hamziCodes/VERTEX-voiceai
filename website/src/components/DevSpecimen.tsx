import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Container } from '@/components/ui';
import { Reveal } from '@/components/motion';

/**
 * SESSION 3 — Beat 4, the developer specimen.
 *
 * Written for the reader who judges the code and not the copy. The snippet is the
 * argument, so it does not type itself out; it fades in as a block, because
 * engineers read code rather than watch it appear.
 *
 * GATE 8 IS OPEN, so this beat ships in its own fallback state — exactly as the
 * story demands: "If the SDK is not published to npm, this beat says `Early
 * access — request a key` and the snippet is labelled as a preview. Never imply
 * `npm install` works when it does not."
 *
 * That means, on purpose:
 * - No `npm install` line anywhere.
 * - The panel is labelled PREVIEW and the card says the API is not final.
 * - The CTA asks for early access instead of handing out a key.
 * - `SDK reference` and `Quickstart` are not links, because those docs do not
 *   exist; only Status points anywhere.
 * - The package name `@ucve/voice-sdk`, the constructor and `calls.create` are the
 *   names from the TypeScript SDK repo. They are UNVERIFIED against a real
 *   published package, but at least the import is correct. When Hamzi confirms gate 8, fix `SNIPPET`, `SDK_VERIFIED` and the CTA in
 *   one pass and this comment stops being true.
 */

const SNIPPET_LINES = [
	"import { Wavia } from '@ucve/voice-sdk';",
	"const wavia = new Wavia({ key: process.env.WAVIA_KEY });",
	'const call = await wavia.calls.create({',
	"  language: 'ur',",
	'  interruptible: true, // on by default',
	'  onTranscript: (line) => console.log(line.text),',
	'});',
	'await call.connect();',
];

/** Flip when the SDK's names, package and publication are actually confirmed. */
const SDK_VERIFIED = false;

const CAPABILITIES = ['Streaming', 'Tool calls', 'Telemetry', 'Webhooks'];

/** One syntax colour only: marigold for strings and keywords, ink for the rest. */
function highlight(line: string) {
	const parts = line.split(/('(?:[^'\\]|\\.)*'|\b(?:import|from|const|await|new|true|default)\b)/g);

	return parts.map((part, i) => {
		const isToken = /^'/.test(part) || /^(import|from|const|await|new|true|default)$/.test(part);
		return (
			<span key={i} style={{ color: isToken ? 'var(--theme-accent)' : 'var(--theme-fg)' }}>
				{part}
			</span>
		);
	});
}

export function DevSpecimen() {
	const [copied, setCopied] = useState(false);
	const timer = useRef<number | undefined>(undefined);

	useEffect(() => () => window.clearTimeout(timer.current), []);

	const copy = async () => {
		const text = SNIPPET_LINES.join('\n');
		try {
			await navigator.clipboard.writeText(text);
			setCopied(true);
			window.clearTimeout(timer.current);
			timer.current = window.setTimeout(() => setCopied(false), 1600);
		} catch {
			/* Clipboard blocked (insecure context or denied). The button stays
			   honest: it does not claim to have copied anything. */
		}
	};

	return (
		<section style={{ borderTop: '1.5px solid var(--theme-border)' }}>
			<Container className="py-20 lg:py-28">
				<div className="grid grid-cols-1 gap-y-12 lg:grid-cols-12 lg:gap-x-14">
					{/* Left: the claim */}
					<div className="lg:col-span-5">
						<p
							style={{
								fontFamily: 'var(--font-mono)',
								fontSize: '0.66rem',
								letterSpacing: '0.14em',
								textTransform: 'uppercase',
								color: 'var(--theme-accent)',
							}}
						>
							04 — Build
						</p>

						<h2
							className="mt-4"
							style={{
								fontFamily: 'var(--font-display)',
								fontWeight: 800,
								fontSize: 'clamp(2rem, 4.2vw, 3.15rem)',
								lineHeight: 1.02,
								letterSpacing: '-0.03em',
								color: 'var(--theme-fg)',
								maxWidth: '18ch',
							}}
						>
							Nine lines to your first call.
						</h2>

						<p
							className="mt-5 max-w-[44ch]"
							style={{ fontSize: '1.05rem', lineHeight: 1.6, color: 'var(--theme-fg-muted)' }}
						>
							Streaming audio in, streaming audio out, and{' '}
							<code
								style={{
									fontFamily: 'var(--font-mono)',
									fontSize: '0.9em',
									color: 'var(--theme-fg)',
								}}
							>
								interruptible
							</code>{' '}
							on by default. Same engine that answers the phone.
						</p>

						{/* Docs that do not exist yet are not links. */}
						<ul
							className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-2"
							style={{
								fontFamily: 'var(--font-mono)',
								fontSize: '0.7rem',
								letterSpacing: '0.06em',
							}}
						>
							{['SDK reference', 'Quickstart'].map((label) => (
								<li
									key={label}
									aria-disabled="true"
									title="Not published yet"
									style={{
										color: 'var(--theme-fg-muted)',
										textDecoration: 'underline',
										textDecorationStyle: 'dashed',
										textDecorationColor: 'var(--theme-border)',
										textUnderlineOffset: 4,
										cursor: 'default',
									}}
								>
									{label}
								</li>
							))}
							<li>
								<Link
									to="/status"
									style={{
										color: 'var(--theme-fg)',
										textDecoration: 'underline',
										textDecorationThickness: 2,
										textUnderlineOffset: 4,
									}}
								>
									Status
								</Link>
							</li>
						</ul>

						<div className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-3">
							<Link
								to="/contact"
								className="inline-flex items-center justify-center font-semibold transition-transform duration-200 hover:-translate-y-0.5"
								style={{
									background: 'var(--theme-fg)',
									color: 'var(--theme-bg)',
									borderRadius: 999,
									padding: '15px 26px',
									fontSize: '0.96rem',
								}}
							>
								Early access — request a key →
							</Link>

							<Link
								to="/core"
								className="transition-colors duration-200"
								style={{
									fontFamily: 'var(--font-mono)',
									fontSize: '0.7rem',
									letterSpacing: '0.06em',
									color: 'var(--theme-fg-muted)',
									textDecoration: 'underline',
									textUnderlineOffset: 4,
									textDecorationColor: 'var(--theme-border)',
								}}
							>
								Everything else it does →
							</Link>
						</div>
					</div>

					{/* Right: the specimen — staged as an object with edges under it,
					    the same way the hero stages its card, rather than a panel
					    floating on the page. */}
					<Reveal className="lg:col-span-7" delay={0.08} y={22} blur={8}>
						<div className="relative">
							<div
								aria-hidden="true"
								className="pointer-events-none absolute inset-x-6 top-3 -bottom-1.5"
								style={{ background: 'var(--theme-surface-2)', border: '1.5px solid var(--theme-border)', borderRadius: 24 }}
							/>
							<div
								aria-hidden="true"
								className="pointer-events-none absolute inset-x-3 top-1.5 -bottom-0.5"
								style={{ background: 'var(--theme-surface)', border: '1.5px solid var(--theme-border)', borderRadius: 24 }}
							/>
						<div
							className="relative z-[1]"
							style={{
								background: 'var(--theme-surface-2)',
								border: '1.5px solid var(--theme-border)',
								borderRadius: 24,
								overflow: 'hidden',
							}}
						>
							<div
								className="flex items-center justify-between gap-3"
								style={{ padding: '12px 16px', borderBottom: '1.5px solid var(--theme-border)' }}
							>
								<p
									style={{
										fontFamily: 'var(--font-mono)',
										fontSize: '0.62rem',
										letterSpacing: '0.12em',
										textTransform: 'uppercase',
										color: 'var(--theme-accent)',
									}}
								>
									Preview · SDK not yet published
								</p>

								<button
									type="button"
									onClick={copy}
									className="cursor-pointer"
									style={{
										fontFamily: 'var(--font-mono)',
										fontSize: '0.62rem',
										letterSpacing: '0.08em',
										textTransform: 'uppercase',
										padding: '5px 11px',
										borderRadius: 999,
										border: '1.5px solid var(--theme-fg)',
										background: copied ? 'var(--theme-fg)' : 'transparent',
										color: copied ? 'var(--theme-bg)' : 'var(--theme-fg)',
										transition: 'background 200ms, color 200ms',
									}}
								>
									{copied ? 'Copied' : 'Copy'}
								</button>
							</div>

							<pre
								className="overflow-x-auto"
								style={{
									margin: 0,
									padding: '18px 18px 20px',
									fontFamily: 'var(--font-mono)',
									fontSize: '0.8rem',
									lineHeight: 1.85,
									tabSize: 2,
								}}
							>
								<code>
									{SNIPPET_LINES.map((line, i) => (
										<div key={i} style={{ display: 'flex', gap: 14 }}>
											<span
												aria-hidden="true"
												style={{
													width: '1.6em',
													flex: '0 0 auto',
													textAlign: 'right',
													color: 'var(--theme-fg-muted)',
													opacity: 0.55,
													userSelect: 'none',
												}}
											>
												{i + 1}
											</span>
											<span>{highlight(line)}</span>
										</div>
									))}
								</code>
							</pre>

							{!SDK_VERIFIED && (
								<div
									style={{
										borderTop: '1.5px solid var(--theme-border)',
										padding: '10px 16px',
									}}
								>
									<p
										style={{
											fontFamily: 'var(--font-mono)',
											fontSize: '0.6rem',
											lineHeight: 1.7,
											color: 'var(--theme-fg-muted)',
										}}
									>
										Preview of the shape, not the published API. The package is not on
										npm yet — request a key and we will send install instructions with it.
									</p>
								</div>
							)}
						</div>
						</div>

						{/* Capabilities — a row of tags, no cards, no icons. */}
						<ul
							className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2"
							style={{
								fontFamily: 'var(--font-mono)',
								fontSize: '0.64rem',
								letterSpacing: '0.1em',
								textTransform: 'uppercase',
								color: 'var(--theme-fg-muted)',
							}}
						>
							{CAPABILITIES.map((cap, i) => (
								<li key={cap} className="flex items-center gap-x-2">
									{i > 0 && (
										<span aria-hidden="true" style={{ color: 'var(--theme-border)' }}>
											·
										</span>
									)}
									<span>{cap}</span>
								</li>
							))}
						</ul>
					</Reveal>
				</div>
			</Container>
		</section>
	);
}
