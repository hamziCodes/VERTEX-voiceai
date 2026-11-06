import type { Metadata } from "next";
import { Bricolage_Grotesque, Instrument_Sans, Instrument_Serif, Space_Mono } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

const displayFont = Bricolage_Grotesque({ display: "swap", subsets: ["latin"], variable: "--font-bricolage" });
const uiFont = Instrument_Sans({ display: "swap", subsets: ["latin"], variable: "--font-instrument-sans" });
const monoFont = Space_Mono({ display: "swap", subsets: ["latin"], variable: "--font-space-mono", weight: ["400", "700"] });
const serifFont = Instrument_Serif({ display: "swap", subsets: ["latin"], variable: "--font-instrument-serif", weight: "400" });

export const metadata: Metadata = {
  title: "Wavia Studio",
  description: "Build, test, connect, and operate Wavia voice agents.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html className={`${displayFont.variable} ${uiFont.variable} ${monoFont.variable} ${serifFont.variable}`} lang="en">
      <body>{children}</body>
    </html>
  );
}
