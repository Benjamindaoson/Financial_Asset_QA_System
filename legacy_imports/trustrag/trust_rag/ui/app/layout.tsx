import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TrustRAG | Evidence-Backed Financial QA",
  description: "Deterministic, traceable answers for financial questions. No hallucination.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased font-sans">{children}</body>
    </html>
  );
}
