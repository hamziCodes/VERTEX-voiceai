import { useEffect, useState } from 'react';
import { ThreadMark, Wordmark } from '@/components/Logo';

/**
 * Boot screen: the thread draws itself once per session, the wordmark stamps in,
 * and it gets out of the way. No glow, no bars — the old seven-bar loader was
 * the same generic voice-AI pictogram the brand mark replaced.
 */
export function LoadingScreen() {
	const [stage, setStage] = useState<'booting' | 'reveal' | 'hide' | 'removed'>('booting');

	useEffect(() => {
		if (sessionStorage.getItem('wavia_booted')) {
			setStage('removed');
			return;
		}

		const t1 = setTimeout(() => setStage('reveal'), 620);
		const t2 = setTimeout(() => {
			setStage('hide');
			sessionStorage.setItem('wavia_booted', 'true');
		}, 1420);
		const t3 = setTimeout(() => setStage('removed'), 1900);

		return () => {
			clearTimeout(t1);
			clearTimeout(t2);
			clearTimeout(t3);
		};
	}, []);

	if (stage === 'removed') return null;

	return (
		<div
			className={`fixed inset-0 z-[150] flex flex-col items-center justify-center transition-opacity duration-500 ease-out ${
				stage === 'hide' ? 'opacity-0 pointer-events-none' : 'opacity-100'
			}`}
			style={{ background: 'var(--theme-bg)' }}
			aria-hidden="true"
		>
			<ThreadMark height={40} />

			<div
				className={`mt-6 transition-all duration-500 ${
					stage === 'booting' ? 'opacity-0 translate-y-2' : 'opacity-100 translate-y-0'
				}`}
			>
				<Wordmark
					className="text-3xl"
					style={{ color: 'var(--theme-fg)', fontWeight: 800 }}
				/>
			</div>

			<div
				className={`mt-3 uppercase transition-opacity duration-500 ${
					stage === 'booting' ? 'opacity-0' : 'opacity-100'
				}`}
				style={{
					fontFamily: 'var(--font-mono)',
					fontSize: '0.68rem',
					letterSpacing: '0.14em',
					color: 'var(--theme-fg-muted)',
				}}
			>
				picking up
			</div>
		</div>
	);
}
