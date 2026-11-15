import { motion } from 'motion/react';
import { Container } from '@/components/ui';
import { Section } from '@/components/ui';

/**
 * SESSION 9 — Beat 9, the privacy page (legal page, /privacy route).
 * Plain, no hero, no glow (audit §2). Simply states the privacy commitments.
 */

export default function Privacy() {
	return (
		<Section
			className="py-16 lg:py-24 border-t border-b border-[var(--theme-border)]"
		>
			<Container className="mx-auto max-w-2xl">
				<h2 className="text-2xl lg:text-3xl font-serif font-medium leading-none tracking-[-0.03em] text-[var(--theme-fg)]">
					Privacy
				</h2>
				<div className="mt-6 text-[var(--theme-fg-muted)]">
					<p>
						Your calls are yours. We never sell your data, and we never use your calls
						to train other AI systems. For the calls you can't get wrong, sensitive data
						stays inside the customer's own boundary — never pooled, never shared,
						never visible to another customer. You can export or delete your data
						anytime from your account settings or by contacting us.
					</p>
					<p className="mt-4">Wavia Core · Wavia Studio · Wavia Shield</p>
				</div>
			</Container>
		</Section>
	);
}