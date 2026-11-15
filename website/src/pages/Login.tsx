import { Link } from 'react-router';
import { motion } from 'motion/react';
import { Btn, Container, H1 } from '@/components/ui';
import { Waveform } from '@/components/Waveform';

export default function Login() {
  const inputStyle: React.CSSProperties = {
    width: '100%',
    borderRadius: '8px',
    border: '1px solid var(--theme-border)',
    background: 'var(--theme-surface-2)',
    padding: '16px',
    fontSize: '1rem',
    color: 'var(--theme-fg)',
    transition: 'border-color 0.3s'
  };

  return (
    <section data-ev-id="ev_1cd32d26fc" className="relative min-h-screen overflow-hidden" style={{ background: 'var(--theme-bg)' }}>
			<div className="hero-glow" />
			<Container className="relative z-10 flex min-h-screen items-center justify-center py-20">
				<motion.div data-ev-id="ev_29dfeee1ff"
        className="flex w-full max-w-[440px] flex-col gap-8"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}>

					<div data-ev-id="ev_5e42cb41fc" className="flex flex-col items-center gap-4">
						<div data-ev-id="ev_34a16cf8d3"
            className="flex items-center justify-center rounded-xl p-4"
            style={{ background: 'var(--theme-accent-soft)' }}>

							<Waveform state="idle" height={40} barCount={7} barWidth={4} gap={4} />
						</div>
						<H1 className="text-center">Welcome back.</H1>
					</div>

					<div data-ev-id="ev_c4c4f4c454"
          className="flex flex-col gap-6 rounded-xl p-8"
          style={{
            background: 'var(--theme-surface)',
            border: '1px solid var(--theme-border)',
            boxShadow: 'none'
          }}>

						<div data-ev-id="ev_145e1e9c88" className="flex flex-col gap-2">
							<label data-ev-id="ev_9c9c99b37a" htmlFor="login-email" className="text-sm font-medium" style={{ color: 'var(--theme-fg)' }}>
								Email
							</label>
							<input data-ev-id="ev_7fb9eb396c"
              id="login-email"
              type="email"
              style={inputStyle}
              placeholder="you@company.com" />

						</div>

						<div data-ev-id="ev_b91201d045" className="flex flex-col gap-2">
							<label data-ev-id="ev_3d61e0e6f8" htmlFor="login-password" className="text-sm font-medium" style={{ color: 'var(--theme-fg)' }}>
								Password
							</label>
							<input data-ev-id="ev_19d50e33c9"
              id="login-password"
              type="password"
              style={inputStyle}
              placeholder="••••••••" />

						</div>

						<Btn className="w-full">Log in →</Btn>

						<p data-ev-id="ev_1569d38468" className="text-center text-sm" style={{ color: 'var(--theme-fg-muted)' }}>
							Accounts aren’t live in this preview yet.{' '}
							<Link data-ev-id="ev_b25e8ec6e0"
              to="/contact"
              className="transition-colors duration-300"
              style={{ color: 'var(--theme-accent)' }}>

								Get in touch
							</Link>{' '}
							and we’ll set you up.
						</p>
					</div>
				</motion.div>
			</Container>
		</section>
  );
}
