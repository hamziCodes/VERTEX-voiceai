import { Container } from '@/components/ui';
import { Reveal } from '@/components/motion';

/**
 * SESSION 9 — Beat 9, the privacy section (homepage).
 * Numeral "09 — Privacy", serif line and four capability rows.
 * No icons, no badges, no certification language anywhere.
 *
 * Register: the quietest beat on the page. The rows are ruled like a
 * schedule rather than boxed like features, and they arrive one after
 * another at reading speed — no lift, no blur-heavy drama, no chips.
 */

const PRIVACY_ROWS = [
  { n: '01', title: 'No-recording mode', body: 'Your calls are never recorded by default. In no-recording mode, no audio is stored or retained.' },
  { n: '02', title: 'Data fencing', body: "Every tenant's data is fenced inside its own boundary — never pooled, never shared, never visible to another customer." },
  { n: '03', title: 'Zero model training', body: 'Your calls are not used to train any external AI model. Period.' },
  { n: '04', title: 'Signed webhooks', body: 'Every event payload is cryptographically signed. You can verify its origin.' },
];

export function PrivacySection() {
  return (
    <section className="py-16 lg:py-24 bg-[--theme-bg] border-t border-b border-[var(--theme-border)]">
      <Container className="mx-auto max-w-2xl">
        <div className="relative flex flex-col gap-6 min-h-[320px]">
          <p className="text-lg font-semibold text-[var(--theme-fg)]"
            style={{ fontFamily: 'var(--font-display)', lineHeight: 1.02 }}
          >
            09 — Privacy
          </p>

          <h2 className="text-2xl font-serif font-medium leading-none tracking-[-0.03em] text-[var(--theme-fg)]">
            Your calls are yours.
          </h2>

          {/* Four ruled rows: one hairline each, arriving in order at reading
              speed. The rule is the only ornament. */}
          <div style={{ borderTop: '1px solid var(--theme-border)' }}>
            {PRIVACY_ROWS.map((row, i) => (
              <Reveal key={row.n} delay={0.14 * i} duration={1} y={14} blur={4}>
                <div
                  className="flex items-start gap-4"
                  style={{
                    borderBottom: '1px solid var(--theme-border)',
                    padding: '18px 0',
                  }}
                >
                  <span className="text-[0.82rem] font-mono tracking-wider"
                    style={{ color: 'var(--theme-accent)', flexShrink: 0, marginTop: 2 }}
                  >
                    {row.n}
                  </span>
                  <div className="flex-1"
                    style={{ lineHeight: 1.6, color: 'var(--theme-fg)' }}
                  >
                    <strong className="font-semibold">{row.title}</strong>
                    <p>{row.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
