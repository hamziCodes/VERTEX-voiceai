import { Container } from '@/components/ui';
import { Link } from 'react-router';

/**
 * Shell-only placeholder for a route that exists in the sitemap but has no
 * beat built yet. It says what it is and what comes next — it never
 * pretends to be the finished page.
 */
export function Placeholder({
	label,
	title,
	note,
	next,
}: {
	label: string;
	title: string;
	note: string;
	next: string;
}) {
	return (
		<Container className="py-24 lg:py-32">
			<p
				className="mb-6"
				style={{
					fontFamily: 'var(--font-mono)',
					fontSize: '0.72rem',
					letterSpacing: '0.12em',
					color: 'var(--theme-accent)',
					textTransform: 'uppercase',
				}}
			>
				{label}
			</p>

			<h1
				style={{
					fontFamily: 'var(--font-display)',
					fontWeight: 800,
					fontSize: 'clamp(2.25rem, 6vw, 4rem)',
					lineHeight: 1.02,
					letterSpacing: '-0.03em',
					color: 'var(--theme-fg)',
				}}
			>
				{title}
			</h1>

			<p
				className="mt-6 max-w-[46ch] text-lg"
				style={{ color: 'var(--theme-fg-muted)' }}
			>
				{note}
			</p>

			<p
				className="mt-10 max-w-[46ch]"
				style={{
					fontFamily: 'var(--font-mono)',
					fontSize: '0.78rem',
					lineHeight: 1.8,
					color: 'var(--theme-fg-muted)',
				}}
			>
				{next}
			</p>

			<div className="mt-10 flex flex-wrap gap-3">
				<Link
					to="/contact"
					className="inline-flex items-center text-sm font-semibold"
					style={{
						background: 'var(--theme-fg)',
						color: 'var(--theme-bg)',
						borderRadius: 'var(--radius-pill)',
						padding: '14px 24px',
					}}
				>
					Book a walkthrough →
				</Link>
				<Link
					to="/"
					className="inline-flex items-center text-sm font-semibold"
					style={{
						background: 'transparent',
						color: 'var(--theme-fg)',
						border: '1.5px solid var(--theme-fg)',
						borderRadius: 'var(--radius-pill)',
						padding: '14px 24px',
					}}
				>
					Back to the shell
				</Link>
			</div>
		</Container>
	);
}
