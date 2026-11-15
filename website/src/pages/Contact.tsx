import { useState } from 'react';
import { Check } from 'lucide-react';
import { motion } from 'motion/react';
import { Btn, Container, Eyebrow, GradientText, H1, Lead, Section } from '@/components/ui';

export default function Contact() {
  const [sent, setSent] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');

  const submit = () => {
    if (!name.trim() || !email.trim() || !message.trim()) return;
    setSent(true);
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    borderRadius: '8px',
    border: '1px solid var(--theme-border)',
    background: 'var(--theme-surface-2)',
    padding: '16px',
    fontSize: '1rem',
    color: 'var(--theme-fg)',
    transition: 'border-color 0.3s, box-shadow 0.3s'
  };

  return (
    <>
			<section data-ev-id="ev_789fb1876d" className="hero relative overflow-hidden">
				<div className="hero-glow" />
				<Container className="relative z-10 pb-10 pt-24 lg:pb-16 lg:pt-32">
					<div data-ev-id="ev_8b3960aee0" className="mx-auto flex max-w-2xl flex-col items-center gap-6 text-center">
						<motion.div data-ev-id="ev_9b925b4374" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
							<Eyebrow>Contact</Eyebrow>
						</motion.div>
						<motion.div data-ev-id="ev_e931a9a207" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
							<H1>
								Tell us what you’re
								<br data-ev-id="ev_964696d99b" />
								<GradientText>trying to do.</GradientText>
							</H1>
						</motion.div>
						<motion.div data-ev-id="ev_8429251160" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
							<Lead>A real person reads every message. Usually replies within one business day.</Lead>
						</motion.div>
					</div>
				</Container>
			</section>

			<Section>
				<motion.div data-ev-id="ev_32c005230b"
        className="mx-auto max-w-xl rounded-xl p-8 lg:p-10"
        style={{
          background: 'var(--theme-surface)',
          border: '1px solid var(--theme-border)',
          boxShadow: 'none'
        }}
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}>

					{sent ?
          <div data-ev-id="ev_cc73cd4eeb" className="flex flex-col items-center gap-4 py-8 text-center">
							<div data-ev-id="ev_6ced78cbbc"
            className="flex h-16 w-16 items-center justify-center rounded-xl"
            style={{ background: 'var(--theme-verify-soft)', color: 'var(--theme-verify)' }}>

								<Check size={28} />
							</div>
							<p data-ev-id="ev_103cf816da" className="font-display text-2xl font-semibold" style={{ color: 'var(--theme-fg)' }}>
								Message received.
							</p>
							<p data-ev-id="ev_178403847c" className="text-base" style={{ color: 'var(--theme-fg-muted)' }}>
								We’ll get back to you at {email}.
							</p>
						</div> :

          <form data-ev-id="ev_210bf20cc9"
          className="flex flex-col gap-6"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}>

							<div data-ev-id="ev_4731e92fe7" className="flex flex-col gap-2">
								<label data-ev-id="ev_f4baf34e4e" htmlFor="name" className="text-sm font-medium" style={{ color: 'var(--theme-fg)' }}>
									Your name
								</label>
								<input data-ev-id="ev_2e32d4b896"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={inputStyle}
              placeholder="Alex Carter"
              required />

							</div>

							<div data-ev-id="ev_7124e4da08" className="flex flex-col gap-2">
								<label data-ev-id="ev_74b535621c" htmlFor="email" className="text-sm font-medium" style={{ color: 'var(--theme-fg)' }}>
									Work email
								</label>
								<input data-ev-id="ev_2c0365f32d"
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              placeholder="alex@company.com"
              required />

							</div>

							<div data-ev-id="ev_419430998e" className="flex flex-col gap-2">
								<label data-ev-id="ev_d58d2fb882" htmlFor="message" className="text-sm font-medium" style={{ color: 'var(--theme-fg)' }}>
									What do you need?
								</label>
								<textarea data-ev-id="ev_9c293c88cd"
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={5}
              style={{ ...inputStyle, resize: 'none' }}
              placeholder="We take about 400 calls a week and want to stop missing them."
              required />

							</div>

							<Btn type="submit" className="w-full">
								Send message →
							</Btn>
						</form>
          }
				</motion.div>
			</Section>
		</>
  );
}
