import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Awaaz Labs Support Chat",
  description: "Local customer support chat prototype"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

