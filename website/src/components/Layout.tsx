import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Nav } from '@/components/Nav';
import { Footer } from '@/components/Footer';
import { LoadingScreen } from '@/components/LoadingScreen';

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="min-h-screen relative" style={{ background: 'var(--theme-bg)' }}>
      {/* Global brand texture grain overlay */}
      <div className="grain" aria-hidden="true" />
      
      {/* Initial boot loader */}
      <LoadingScreen />

      <Nav />
      {/* 80px bar + the 1.5px ink rule it sits on. */}
      <main style={{ paddingTop: 82 }}>{children}</main>
      <Footer />
    </div>
  );
}
