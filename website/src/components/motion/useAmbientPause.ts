import { useEffect, type RefObject } from 'react';

/**
 * Stops the fold's ambient loops when nobody is looking at them.
 *
 * Ambient motion is cheap, but it is not free: a hero that keeps bobbing and
 * travelling while the visitor reads Beat 7 is wasted battery and a stray
 * compositor frame budget. This flips `data-ambient` on the element between
 * `live` and `paused`; `theme.css` turns that into `animation-play-state`
 * for every `[data-ambient-loop]` descendant.
 *
 * Deliberately attribute-based and ref-driven: no state, so nothing re-renders
 * when the fold leaves the viewport.
 */
export function useAmbientPause(ref: RefObject<HTMLElement | null>) {
	useEffect(() => {
		const el = ref.current;
		if (!el) return;

		let inView = true;

		const sync = () => {
			el.setAttribute('data-ambient', inView && !document.hidden ? 'live' : 'paused');
		};

		const observer = new IntersectionObserver(
			([entry]) => {
				inView = entry.isIntersecting;
				sync();
			},
			{ threshold: 0 },
		);

		observer.observe(el);
		document.addEventListener('visibilitychange', sync);
		sync();

		return () => {
			observer.disconnect();
			document.removeEventListener('visibilitychange', sync);
		};
	}, [ref]);
}
