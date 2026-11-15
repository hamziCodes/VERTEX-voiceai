import { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useSpring } from 'motion/react';
import { Container } from '@/components/ui';
import { Reveal } from '@/components/motion';

/**
 * SESSION 11 — Beat 11, the enterprise/Shield section (homepage).
 * Numeral "11 — Shield", headline and four-step white-glove timeline.
 * No badges, no certification language, no HIPAA/SOC 2/GDPR claims anywhere.
 * Slower and quieter than other beats: timeline draws once, no pin, one brass accent.
 *
 * The timeline's spine is the only thing that moves: it draws down the steps
 * as the reader scrolls past them, so the four-step process arrives in the
 * order it happens. Off under reduced motion — the spine is simply drawn.
 */

const TIMELINE_STEPS = [
  { n: '1', label: 'Scope', body: 'We map your calls, compliance needs, and integration points with a named solutions architect.' },
  { n: '2', label: 'Build', body: 'We configure the dedicated VPC or on-prem deployment, SIP trunking into your existing PBX.' },
  { n: '3', label: 'Deploy in your perimeter', body: 'We deploy in your perimeter. One named engineer answers and owns the hand-off.' },
  { n: '4', label: 'Own it with a named architect', body: 'You have a named architect for ongoing support. No hand-offs, no vendor seams.' },
];

export function EnterpriseSection() {
  const reduced = useReducedMotion() ?? false;
  const timelineRef = useRef<HTMLDivElement>(null);

  // 0 when the timeline enters, 1 once its last step has been read.
  const { scrollYProgress } = useScroll({ target: timelineRef, offset: ['start 82%', 'end 62%'] });
  const draw = useSpring(scrollYProgress, { stiffness: 70, damping: 24, mass: 0.4 });

  return (
    <section className="py-16 lg:py-24 bg-[--theme-bg] border-t border-b border-[var(--theme-border)]">
      <Container className="mx-auto max-w-2xl">
        <div className="relative flex flex-col gap-6 min-h-[360px]">
          <p className="text-lg font-semibold text-[var(--theme-fg)]"
            style={{ fontFamily: 'var(--font-display)', lineHeight: 1.02 }}
          >
            11 — Shield
          </p>

          <h2 className="text-2xl font-serif font-medium leading-none tracking-[-0.03em] text-[var(--theme-fg)]">
            For the calls you can't get wrong.
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div>
              <p className="text-[1.2rem] font-medium text-[var(--theme-fg)]"
                style={{ fontFamily: 'var(--font-display)', lineHeight: 1.05 }}
              >
                Dedicated infrastructure
              </p>
              <ul className="mt-4 space-y-3 text-[var(--theme-fg-muted)]" style={{ lineHeight: 1.6, fontSize: '0.98rem' }}>
                <li>Dedicated VPC or on-prem deployment</li>
                <li>SIP trunking into the PBX they already own</li>
                <li>One named engineer who answers</li>
              </ul>
            </div>
            <div>
              <p className="text-[1.2rem] font-medium text-[var(--theme-fg)]"
                style={{ fontFamily: 'var(--font-display)', lineHeight: 1.05 }}
              >
                White-glove timeline
              </p>

              <div ref={timelineRef} className="relative mt-4">
                {/* The spine, drawn as the reader passes the steps. Sits outside
                    the list's own box so nothing in the list can shift. */}
                <div
                  aria-hidden="true"
                  style={{
                    position: 'absolute',
                    left: -14,
                    top: 6,
                    bottom: 6,
                    width: 1.5,
                    borderRadius: 999,
                    background: 'var(--theme-border)',
                  }}
                />
                <motion.div
                  aria-hidden="true"
                  style={{
                    position: 'absolute',
                    left: -14,
                    top: 6,
                    bottom: 6,
                    width: 1.5,
                    borderRadius: 999,
                    background: 'var(--theme-accent)',
                    transformOrigin: '50% 0',
                    scaleY: reduced ? 1 : draw,
                  }}
                />

                <ol className="space-y-3" style={{ lineHeight: 1.6, fontSize: '0.98rem' }}>
                  {TIMELINE_STEPS.map((step) => (
                    <li key={step.n} className="flex items-start gap-2"
                      style={{ display: 'flex', alignItems: 'flex-start' }}
                    >
                      <span className="text-[0.82rem] font-mono tracking-wider"
                        style={{ color: 'var(--theme-accent)', flexShrink: 0, marginTop: 4 }}
                      >
                        {step.n}</span>
                      <div>
                        <strong className="font-semibold">{step.label}</strong>
                        <p>{step.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>

          {/* The offer. Arrives last, on its own, after the timeline has drawn. */}
          <Reveal delay={0.1} y={16} blur={6} className="mt-8 text-center">
            <a
              href="/contact"
              className="inline-flex items-center justify-center font-semibold transition-transform duration-200 hover:-translate-y-0.5"
              style={{ background: 'var(--theme-fg)', color: 'var(--theme-bg)', borderRadius: 999, padding: '15px 28px', fontSize: '0.98rem' }}
            >
              Scope it with our team →
            </a>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
