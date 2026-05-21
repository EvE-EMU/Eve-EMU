import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EvE-EMU",
  description:
    "Public market tools for WOMPSTAR (3-FKCZ), plus member services via Alliance Auth — spreads, browser, and corp integrations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
