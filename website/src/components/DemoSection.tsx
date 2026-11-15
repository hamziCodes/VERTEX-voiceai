import { Container } from '@/components/ui';
import { BranchingDemo } from '@/components/BranchingDemo';

/**
 * Scene 5 hand-off — "Your turn."
 *
 * The pinned journey (Scenes 0–4) unpins into the existing interactive
 * branching demo, untouched: same component, same four-language script tree,
 * same interruption branches, same honesty labels. This wrapper only frames
 * it. The full Scene 5 treatment (setup steps as stations around the demo)
 * belongs to the next build stage, not this pilot.
 */
export function DemoSection() {
	return (
		<section id="demo" style={{ scrollMarginTop: 96, padding: '72px 0 84px' }}>
			<Container>
				<div style={{ maxWidth: 760, margin: '0 auto' }}>
					<p
						style={{
							fontFamily: 'var(--font-mono)',
							fontSize: '0.68rem',
							letterSpacing: '0.14em',
							textTransform: 'uppercase',
							color: 'var(--theme-accent)',
						}}
					>
						Your turn
					</p>
					<h2
						style={{
							fontFamily: 'var(--font-display)',
							fontWeight: 700,
							fontSize: 'clamp(1.9rem, 4.5vw, 2.9rem)',
							lineHeight: 1.05,
							letterSpacing: '-0.03em',
							color: 'var(--theme-fg)',
							marginTop: 14,
						}}
					>
						The same call — now you play the caller.
					</h2>
					<div className="mt-9">
						<BranchingDemo />
					</div>
				</div>
			</Container>
		</section>
	);
}
