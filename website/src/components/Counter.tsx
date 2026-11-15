import { useEffect, useRef, useState } from 'react';
import { useInView, animate } from 'motion/react';

interface CounterProps {
  value: string;
  className?: string;
  style?: React.CSSProperties;
}

export function Counter({ value, className = '', style }: CounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  const [displayValue, setDisplayValue] = useState<string>(value);

  useEffect(() => {
    if (!inView) return;

    // Parse prefix, numeric value, decimal places, suffix
    const match = value.match(/^([^0-9.]*)([0-9]+(?:\.[0-9]+)?)(.*)$/);
    if (!match) {
      setDisplayValue(value);
      return;
    }

    const prefix = match[1];
    const targetNum = parseFloat(match[2]);
    const suffix = match[3];
    const decimals = match[2].includes('.') ? match[2].split('.')[1].length : 0;

    if (targetNum === 0) {
      setDisplayValue(value);
      return;
    }

    const controls = animate(0, targetNum, {
      duration: 1.6,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => {
        setDisplayValue(`${prefix}${latest.toFixed(decimals)}${suffix}`);
      },
      onComplete: () => {
        setDisplayValue(value);
      },
    });

    return () => controls.stop();
  }, [inView, value]);

  return (
    <span ref={ref} className={className} style={style}>
      {displayValue}
    </span>
  );
}
