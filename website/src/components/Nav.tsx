import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router';
import { Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Logo } from '@/components/Logo';
import { Container } from '@/components/ui';

/**
 * Six links, one CTA, no dropdowns. Three sub-brands do not justify a
 * mega-menu. "Log in" is deliberately absent until the Studio app exists —
 * the marketing site never collects credentials.
 */
const LINKS = [
	{ to: '/core', label: 'Wavia Core' },
	{ to: '/studio', label: 'Wavia Studio' },
	{ to: '/shield', label: 'Wavia Shield' },
	{ to: '/pricing', label: 'Pricing' },
	{ to: '/about', label: 'About' },
];

export function Nav() {
	const [open, setOpen] = useState(false);
	const { pathname } = useLocation();

	// Close the sheet on navigation, including back/forward.
	useEffect(() => setOpen(false), [pathname]);

	useEffect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setOpen(false);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [open]);

	return (
		<header
			className="fixed inset-x-0 top-0 z-50"
			style={{
				background: 'var(--theme-bg)',
				borderBottom: '1.5px solid var(--theme-fg)',
			}}
		>
			<Container className="flex h-20 items-center justify-between gap-8">
				<Logo size="md" />

				<nav className="hidden items-center gap-7 lg:flex" aria-label="Primary">
					{LINKS.map((l) => (
						<NavLink
							key={l.to}
							to={l.to}
							className="text-[0.95rem] font-medium transition-colors duration-200"
							style={({ isActive }) => ({
								color: isActive ? 'var(--theme-accent)' : 'var(--theme-fg)',
							})}
						>
							{l.label}
						</NavLink>
					))}
					<span
						className="text-[0.95rem] font-medium cursor-not-allowed"
						style={{ color: 'var(--theme-fg-muted)', opacity: 0.6 }}
						title="Docs coming with early access"
						aria-disabled="true"
					>
						Docs
					</span>
				</nav>

				<div className="hidden lg:flex">
					<Link
						to="/contact"
						className="inline-flex items-center gap-2 text-[0.95rem] font-semibold transition-colors duration-200"
						style={{
							background: 'var(--theme-fg)',
							color: 'var(--theme-bg)',
							borderRadius: 'var(--radius-pill)',
							padding: '14px 24px',
						}}
					>
						Book a walkthrough →
					</Link>
				</div>

				<button
					type="button"
					className="lg:hidden p-2 cursor-pointer"
					style={{ color: 'var(--theme-fg)' }}
					onClick={() => setOpen((v) => !v)}
					aria-label={open ? 'Close menu' : 'Open menu'}
					aria-expanded={open}
					aria-controls="mobile-menu"
				>
					{open ? <X size={24} /> : <Menu size={24} />}
				</button>
			</Container>

			<AnimatePresence>
				{open && (
					<motion.div
						id="mobile-menu"
						initial={{ height: 0, opacity: 0 }}
						animate={{ height: 'auto', opacity: 1 }}
						exit={{ height: 0, opacity: 0 }}
						transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
						className="overflow-hidden lg:hidden"
						style={{
							background: 'var(--theme-bg)',
							borderTop: '1.5px solid var(--theme-border)',
						}}
					>
						<Container className="flex flex-col gap-1 py-5">
							{LINKS.map((l) => (
								<Link
									key={l.to}
									to={l.to}
									onClick={() => setOpen(false)}
									className="text-lg font-medium py-2.5"
									style={{ color: 'var(--theme-fg)', fontFamily: 'var(--font-display)' }}
								>
									{l.label}
								</Link>
							))}
							<span
								className="text-lg font-medium py-2.5 cursor-not-allowed"
								style={{ color: 'var(--theme-fg-muted)', opacity: 0.6, fontFamily: 'var(--font-display)' }}
								aria-disabled="true"
							>
								Docs — soon
							</span>
							<Link
								to="/contact"
								onClick={() => setOpen(false)}
								className="mt-3 inline-flex w-full items-center justify-center text-base font-semibold"
								style={{
									background: 'var(--theme-fg)',
									color: 'var(--theme-bg)',
									borderRadius: 'var(--radius-pill)',
									padding: '16px 24px',
								}}
							>
								Book a walkthrough →
							</Link>
						</Container>
					</motion.div>
				)}
			</AnimatePresence>
		</header>
	);
}
