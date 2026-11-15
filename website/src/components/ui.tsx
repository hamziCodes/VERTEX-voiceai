import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { motion } from 'motion/react';

type Variant = 'primary' | 'outline' | 'ghost';

// Brand kit rule: 8px radius on every button — never a full pill.
const base =
  'inline-flex items-center justify-center gap-2 rounded-lg font-semibold text-[0.98rem] leading-none transition-all duration-200 ease-out select-none cursor-pointer';

export function BtnLink({
  to,
  children,
  variant = 'primary',
  className = '',
}: {
  to: string;
  children: ReactNode;
  variant?: Variant;
  className?: string;
}) {
  const styles: Record<Variant, React.CSSProperties> = {
    primary: {
      background: 'var(--theme-accent)',
      color: '#15120D',
      padding: '14px 28px',
      border: '1px solid transparent',
    },
    outline: {
      background: 'transparent',
      color: 'var(--theme-fg)',
      padding: '14px 28px',
      border: '1px solid var(--theme-border)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--theme-fg-muted)',
      padding: '14px 20px',
      border: '1px solid transparent',
    },
  };

  return (
    <Link
      to={to}
      className={`${base} ${
        variant === 'primary'
          ? 'hover:-translate-y-0.5 hover:shadow-[0_4px_20px_var(--theme-accent-soft)]'
          : variant === 'outline'
          ? 'hover:border-[var(--theme-accent)] hover:-translate-y-0.5'
          : 'hover:text-[var(--theme-fg)]'
      } ${className}`}
      style={styles[variant]}
    >
      {children}
    </Link>
  );
}

export function Btn({
  children,
  variant = 'primary',
  className = '',
  onClick,
  type = 'button',
  disabled,
}: {
  children: ReactNode;
  variant?: Variant;
  className?: string;
  onClick?: () => void;
  type?: 'button' | 'submit';
  disabled?: boolean;
}) {
  const styles: Record<Variant, React.CSSProperties> = {
    primary: {
      background: 'var(--theme-accent)',
      color: '#15120D',
      padding: '14px 28px',
      border: '1px solid transparent',
    },
    outline: {
      background: 'transparent',
      color: 'var(--theme-fg)',
      padding: '14px 28px',
      border: '1px solid var(--theme-border)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--theme-fg-muted)',
      padding: '14px 20px',
      border: '1px solid transparent',
    },
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${
        variant === 'primary'
          ? 'hover:-translate-y-0.5 hover:shadow-[0_4px_20px_var(--theme-accent-soft)]'
          : variant === 'outline'
          ? 'hover:border-[var(--theme-accent)] hover:-translate-y-0.5'
          : 'hover:text-[var(--theme-fg)]'
      } disabled:opacity-50 disabled:hover:translate-y-0 disabled:cursor-not-allowed ${className}`}
      style={styles[variant]}
    >
      {children}
    </button>
  );
}

// Brand kit rule: max-width 1120px
export function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1120px] px-6 ${className}`}>{children}</div>;
}

// Brand kit rule: 4px grid rhythm
export function Section({
  children,
  className = '',
  id,
  style,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
  style?: React.CSSProperties;
}) {
  return (
    <section id={id} className={`py-16 lg:py-24 border-b border-[var(--theme-border)] last:border-b-0 ${className}`} style={style}>
      <Container>{children}</Container>
    </section>
  );
}

// Brand kit rule: The pill shape is earned by category tags/eyebrows, nothing else
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <motion.p
      className="inline-flex items-center gap-2 rounded-full px-3.5 py-1 font-mono text-xs font-semibold uppercase tracking-wider border border-[var(--theme-border)] bg-[var(--theme-surface-2)] text-[var(--theme-fg-muted)]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {children}
    </motion.p>
  );
}

export function H1({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h1
      className={`font-display text-[2.75rem] font-bold lg:text-[3.4rem] tracking-tight ${className}`}
      style={{
        lineHeight: 1.1,
        color: 'var(--theme-fg)',
      }}
    >
      {children}
    </h1>
  );
}

export function H2({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h2
      className={`font-display text-[1.75rem] font-semibold lg:text-[2.1rem] tracking-tight ${className}`}
      style={{
        lineHeight: 1.2,
        color: 'var(--theme-fg)',
      }}
    >
      {children}
    </h2>
  );
}

export function H3({
  children,
  className = '',
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <h3
      className={`font-display text-[1.25rem] font-semibold lg:text-[1.4rem] tracking-tight ${className}`}
      style={{ lineHeight: 1.3, color: 'var(--theme-fg)', ...style }}
    >
      {children}
    </h3>
  );
}

export function Lead({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={`text-[1.15rem] leading-relaxed max-w-[58ch] ${className}`}
      style={{ color: 'var(--theme-fg-muted)' }}
    >
      {children}
    </p>
  );
}

// Brand kit rule: Flat surfaces, 1px borders, 8–12px radius, shadow earned on hover only
export function Card({
  children,
  className = '',
  hover = true,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <motion.div
      className={`rounded-xl p-6 lg:p-8 bg-[var(--theme-surface)] border border-[var(--theme-border)] transition-colors duration-200 ${className}`}
      whileHover={
        hover
          ? {
              y: -2,
              boxShadow: 'var(--theme-shadow)',
              borderColor: 'var(--theme-accent)',
            }
          : undefined
      }
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  );
}

// Alias for backwards compatibility
export const GlassCard = Card;

// Highlighted keyword in text
export function GradientText({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`text-[var(--theme-accent)] font-bold ${className}`}>
      {children}
    </span>
  );
}
