import { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import type { CSSProperties } from 'react';
import {
	DEMO_LANGS,
	DEMO_NODES,
	DEMO_START,
	LANG_CLASS,
	RTL_LANGS,
	type DemoLang,
	type DemoLine,
	type DemoOption,
} from '@/content/demo';

/**
 * Beat 1 demo card — scripted, branching, transcript-only, four languages.
 *
 * What it must never do: call itself live, show a microphone it will not use, or
 * present a recording that does not exist. Recordings are gate 8.5; until they
 * land this card is explicitly a script tree, and the visitor drives the caller.
 *
 * All four chips are enabled because the demo is text and text needs no audio —
 * which is the whole point of a four-language product. Switching language swaps
 * the transcript in place; the branch you are standing on does not move, so the
 * same clinic call reads correctly in Urdu, English, Arabic and Malay.
 *
 * The interruption branch is the point of the whole beat: pick it and the trace
 * truncates mid-line, because "you can talk over it" is the claim that separates
 * this product from every chatbot on the internet.
 */

const BAR_COUNT = 46;

// Deterministic pseudo-random heights so the trace looks drawn, not generated
// differently on every render.
const BARS = Array.from({ length: BAR_COUNT }, (_, i) => {
	const n = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1;
	return 0.18 + n * 0.82;
});

type TraceState = 'idle' | 'playing' | 'cut';

function Trace({ state, reduced }: { state: TraceState; reduced: boolean }) {
	const cutAt = Math.floor(BAR_COUNT * 0.56);

	return (
		<div
			className="relative flex items-center justify-center gap-[3px] overflow-hidden"
			style={{
				height: 76,
				padding: '0 22px',
				background: 'var(--theme-surface-2)',
				borderBottom: '1.5px solid var(--theme-border)',
			}}
			aria-hidden="true"
		>
			{BARS.map((h, i) => {
				const afterCut = state === 'cut' && i >= cutAt;
				const height = afterCut ? 8 : Math.round(h * 46);

				return (
					<span
						key={i}
						data-ambient-loop={reduced ? undefined : ''}
						style={{
							display: 'block',
							width: 2,
							height,
							borderRadius: 2,
							background: afterCut ? 'var(--theme-fg-muted)' : 'var(--theme-accent)',
							opacity: afterCut ? 0.35 : 1,
							transformOrigin: 'center',
							/* Idle: slow, shallow breathing so the card is live at rest.
							   Playing: the stronger speak-wave, unchanged. */
							animation: reduced
								? undefined
								: state === 'playing'
									? `speak-wave 1.1s ease-in-out ${(-(i * 0.045)).toFixed(3)}s infinite`
									: `wave-idle ${(3.1 + (i % 7) * 0.16).toFixed(2)}s ease-in-out ${(-(i * 0.06)).toFixed(2)}s infinite`,
						}}
					/>
				);
			})}

			{state === 'cut' && (
				<span
					className="absolute top-0 bottom-0"
					style={{ left: `calc(22px + ${cutAt * 5}px)`, width: 2, background: 'var(--theme-fg)' }}
				/>
			)}
		</div>
	);
}

/** Each script gets its own face and its own leading. Latin text is never
 *  forced into a 2.0 line-height, and Urdu is never given Arabic's Naskh face. */
function scriptStyle(lang: DemoLang, kind: 'line' | 'option'): CSSProperties {
	if (lang === 'ur') {
		return kind === 'line'
			? { fontSize: '1.1rem', lineHeight: 2.05 }
			: { fontSize: '1rem', lineHeight: 2 };
	}
	if (lang === 'ar') {
		return kind === 'line'
			? { fontSize: '1.1rem', lineHeight: 1.95 }
			: { fontSize: '1rem', lineHeight: 1.8 };
	}
	return kind === 'line'
		? { fontSize: '0.98rem', lineHeight: 1.55 }
		: { fontSize: '0.92rem', lineHeight: 1.4 };
}

/** `onActivityChange` reports whether Wavia is mid-sentence, so decorative
 *  surroundings (the hero thread) can react without owning demo state. */
export function BranchingDemo({
	onActivityChange,
}: {
	onActivityChange?: (active: boolean) => void;
}) {
	const [lang, setLang] = useState<DemoLang>('ur');
	const [nodeId, setNodeId] = useState(DEMO_START);
	const [history, setHistory] = useState<DemoLine[]>([DEMO_NODES[DEMO_START].line]);
	const [trace, setTrace] = useState<TraceState>('playing');
	const reduced = useReducedMotion() ?? false;

	const scrollRef = useRef<HTMLDivElement>(null);
	const timers = useRef<number[]>([]);

	const isRtl = RTL_LANGS.includes(lang);

	const clearTimers = () => {
		timers.current.forEach((t) => window.clearTimeout(t));
		timers.current = [];
	};

	useEffect(() => () => clearTimers(), []);

	useEffect(() => {
		onActivityChange?.(trace !== 'idle');
	}, [trace, onActivityChange]);

	// The trace settles after the assistant's line has been "spoken".
	useEffect(() => {
		if (trace === 'idle') return;
		const t = window.setTimeout(() => setTrace('idle'), trace === 'cut' ? 900 : 750);
		timers.current.push(t);
		return () => window.clearTimeout(t);
	}, [trace, history.length]);

	useEffect(() => {
		const el = scrollRef.current;
		if (el) el.scrollTop = el.scrollHeight;
	}, [history]);

	const node = DEMO_NODES[nodeId];

	const pick = (option: DemoOption) => {
		clearTimers();

		setHistory((prev) => {
			const next = [...prev];

			// An interruption truncates the line that was being spoken.
			if (option.interrupt) {
				for (let i = next.length - 1; i >= 0; i -= 1) {
					if (next[i].from === 'wavia') {
						next[i] = { ...next[i], cutAfterMs: 420 };
						break;
					}
				}
			}

			next.push({ from: 'caller', text: option.text });

			const target = DEMO_NODES[option.next];
			if (target) next.push(target.line);

			return next;
		});

		setNodeId(option.next);
		setTrace(option.interrupt ? 'cut' : 'playing');
	};

	const reset = () => {
		clearTimers();
		setNodeId(DEMO_START);
		setHistory([DEMO_NODES[DEMO_START].line]);
		setTrace('playing');
	};

	const done = !node.options || node.options.length === 0;

	return (
		<div
			style={{
				background: 'var(--theme-surface)',
				border: '1.5px solid var(--theme-border)',
				borderRadius: 32,
				boxShadow: 'var(--theme-shadow)',
				overflow: 'hidden',
			}}
		>
			{/* Head */}
			<div
				className="flex flex-col gap-2.5"
				style={{ padding: '15px 20px 14px', borderBottom: '1.5px solid var(--theme-border)' }}
			>
				<p
					style={{
						fontFamily: 'var(--font-mono)',
						fontSize: '0.66rem',
						letterSpacing: '0.1em',
						textTransform: 'uppercase',
						color: 'var(--theme-accent)',
					}}
				>
					Scripted demo · transcript, no audio yet
				</p>

				<div className="flex flex-wrap items-center gap-1.5">
					{DEMO_LANGS.map((l) => {
						const active = l.code === lang;
						return (
							<button
								key={l.code}
								type="button"
								onClick={() => setLang(l.code)}
								className="cursor-pointer"
								style={{
									fontFamily: 'var(--font-mono)',
									fontSize: '0.66rem',
									letterSpacing: '0.04em',
									padding: '5px 10px',
									borderRadius: 999,
									border: `1.5px solid ${active ? 'var(--theme-fg)' : 'var(--theme-border)'}`,
									background: active ? 'var(--theme-fg)' : 'transparent',
									color: active ? 'var(--theme-bg)' : 'var(--theme-fg-muted)',
								}}
								aria-pressed={active}
								lang={l.code}
							>
								{l.label}
							</button>
						);
					})}
				</div>
			</div>

			<Trace state={trace} reduced={reduced} />

			{/* Transcript */}
			<div
				ref={scrollRef}
				className="flex flex-col gap-4 overflow-y-auto"
				style={{ padding: '20px', minHeight: 186, maxHeight: 300 }}
				aria-live="polite"
			>
				{history.map((line, i) => {
					const text = line.text[lang];
					const isWavia = line.from === 'wavia';

					return (
						<motion.div
							key={`${i}-${line.from}`}
							initial={reduced ? false : { opacity: 0, y: 6 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
							className={isWavia ? '' : 'pl-5'}
						>
							<div className="flex items-baseline gap-2">
								<span
									style={{
										fontFamily: 'var(--font-mono)',
										fontSize: '0.6rem',
										letterSpacing: '0.12em',
										textTransform: 'uppercase',
										color: isWavia ? 'var(--theme-accent)' : 'var(--theme-fg-muted)',
									}}
								>
									{isWavia ? 'wavia' : 'caller'}
								</span>
								{line.cutAfterMs && (
									<span
										style={{
											fontFamily: 'var(--font-mono)',
											fontSize: '0.58rem',
											letterSpacing: '0.08em',
											color: 'var(--theme-fg)',
											background: 'var(--theme-accent-soft)',
											borderRadius: 4,
											padding: '1px 5px',
										}}
									>
										interrupted at {(line.cutAfterMs / 1000).toFixed(1)}s
									</span>
								)}
							</div>

							<p
								className={LANG_CLASS[lang]}
								lang={lang}
								dir={isRtl ? 'rtl' : 'ltr'}
								style={{
									...scriptStyle(lang, 'line'),
									color: 'var(--theme-fg)',
									textDecoration: line.cutAfterMs ? 'line-through' : undefined,
									textDecorationColor: 'var(--theme-border)',
									textAlign: isRtl ? 'right' : 'left',
								}}
							>
								{text}
							</p>
						</motion.div>
					);
				})}
			</div>

			{/* Caller turns */}
			<div style={{ borderTop: '1.5px solid var(--theme-border)', padding: '16px 20px 18px' }}>
				<p
					style={{
						fontFamily: 'var(--font-mono)',
						fontSize: '0.62rem',
						letterSpacing: '0.1em',
						textTransform: 'uppercase',
						color: 'var(--theme-fg-muted)',
						marginBottom: 10,
					}}
				>
					{done ? 'End of script' : 'You are the caller — pick a line'}
				</p>

				{done ? (
					<button
						type="button"
						onClick={reset}
						className="cursor-pointer"
						style={{
							fontFamily: 'var(--font-mono)',
							fontSize: '0.72rem',
							padding: '11px 18px',
							borderRadius: 999,
							border: '1.5px solid var(--theme-fg)',
							background: 'transparent',
							color: 'var(--theme-fg)',
						}}
					>
						Run it again
					</button>
				) : (
					<div className="flex flex-col gap-2">
						{node.options!.map((o, i) => (
							<button
								key={`${nodeId}-${i}`}
								type="button"
								onClick={() => pick(o)}
								className="group cursor-pointer text-left transition-colors duration-150"
								style={{
									border: '1.5px solid var(--theme-border)',
									borderRadius: 999,
									padding: '10px 16px',
									background: 'transparent',
									color: 'var(--theme-fg)',
								}}
								onMouseEnter={(e) => {
									e.currentTarget.style.borderColor = 'var(--theme-fg)';
								}}
								onMouseLeave={(e) => {
									e.currentTarget.style.borderColor = 'var(--theme-border)';
								}}
							>
								<span
									className={LANG_CLASS[lang] ? `${LANG_CLASS[lang]} block` : 'block'}
									lang={lang}
									dir={isRtl ? 'rtl' : 'ltr'}
									style={{
										...scriptStyle(lang, 'option'),
										textAlign: isRtl ? 'right' : 'left',
									}}
								>
									{o.text[lang]}
								</span>
								{o.interrupt && (
									<span
										style={{
											display: 'block',
											marginTop: 2,
											fontFamily: 'var(--font-mono)',
											fontSize: '0.58rem',
											letterSpacing: '0.08em',
											color: 'var(--theme-accent)',
											textAlign: isRtl ? 'right' : 'left',
										}}
									>
										interrupts
									</span>
								)}
							</button>
						))}
					</div>
				)}
			</div>

			<div
				style={{
					borderTop: '1.5px solid var(--theme-border)',
					padding: '10px 20px',
					background: 'var(--theme-surface-2)',
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
					Real engine recordings replace this transcript once they are captured. Nothing
					here is a live session, and no microphone is requested.
				</p>
			</div>
		</div>
	);
}
