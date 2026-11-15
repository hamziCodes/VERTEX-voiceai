import { Link } from 'react-router';
import { Wordmark } from '@/components/Logo';
import { Container } from '@/components/ui';

/**
 * Beat 12 shell: full-bleed marigold band, cream small type, and the giant
 * wordmark clipped by the bottom edge — the page's recall device.
 *
 * Contrast note: #FFF6E5 on #B45309 is 4.53:1, so every small string here is
 * cream. Ink (#1C1408) is used only for the wordmark, which is large enough
 * (~28vw) that 3:1 applies. Do not set ink small text on this band.
 */

const COLUMNS = [
	{
		title: 'Product',
		links: [
			{ to: '/studio', label: 'Wavia Studio' },
			{ to: '/core', label: 'Wavia Core' },
			{ to: '/shield', label: 'Wavia Shield' },
			{ to: '/pricing', label: 'Pricing' },
		],
	},
	{
		title: 'Developers',
		links: [
			{ to: '/core', label: 'SDK & reference' },
			{ to: '/how-it-works', label: 'How it works' },
			{ to: '/contact', label: 'Request early access' },
		],
	},
	{
		title: 'Company',
		links: [
			{ to: '/about', label: 'About' },
			{ to: '/contact', label: 'Contact' },
			{ to: '/status', label: 'Status' },
		],
	},
	{
		title: 'Legal',
		links: [
			{ to: '/privacy', label: 'Privacy' },
			{ to: '/terms', label: 'Terms' },
		],
	},
];

export function Footer() {
	const cream = 'var(--theme-bg)';

	return (
		<footer style={{ background: 'var(--theme-accent)', color: cream }}>
			<Container className="pt-16 lg:pt-20">
				<div className="grid gap-10 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
					<div className="flex flex-col gap-5">
						<p
							className="max-w-[26ch] text-[1.5rem] leading-[1.25] lg:text-[1.75rem]"
							style={{ fontFamily: 'var(--font-display)', fontWeight: 700, letterSpacing: '-0.02em' }}
						>
							Where the conversation actually happens.
						</p>
						<Link
							to="/contact"
							className="inline-flex w-fit items-center gap-2 text-sm font-semibold"
							style={{
								background: cream,
								color: 'var(--theme-accent)',
								borderRadius: 'var(--radius-pill)',
								padding: '12px 20px',
							}}
						>
							Book a walkthrough →
						</Link>
					</div>

					{COLUMNS.map((col) => (
						<div key={col.title} className="flex flex-col gap-3.5">
							<p
								className="text-[0.7rem] uppercase"
								style={{
									fontFamily: 'var(--font-mono)',
									letterSpacing: '0.12em',
									opacity: 0.75,
								}}
							>
								{col.title}
							</p>
							<ul className="flex flex-col gap-2.5">
								{col.links.map((l) => (
									<li key={`${col.title}-${l.to}-${l.label}`}>
										<Link
											to={l.to}
											className="text-[0.95rem] transition-opacity duration-200 hover:opacity-70"
										>
											{l.label}
										</Link>
									</li>
								))}
							</ul>
						</div>
					))}
				</div>

				<div
					className="mt-14 flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between"
					style={{
						borderTop: `1.5px solid color-mix(in srgb, ${cream} 35%, transparent)`,
						fontFamily: 'var(--font-mono)',
						fontSize: '0.72rem',
						letterSpacing: '0.02em',
					}}
				>
					<p>© {new Date().getFullYear()} Wavia</p>
					<p>Wavia Core · Wavia Studio · Wavia Shield</p>
				</div>
			</Container>

			{/* Giant wordmark, clipped by the bottom of the page. */}
			<div className="relative mt-10 overflow-hidden" aria-hidden="true">
				<Wordmark
					dotColor={cream}
					className="block w-full text-center"
					style={{
						fontSize: 'clamp(5rem, 28vw, 26rem)',
						fontWeight: 800,
						color: 'var(--theme-fg)',
						marginBottom: '-0.18em',
					}}
				/>
			</div>
		</footer>
	);
}
