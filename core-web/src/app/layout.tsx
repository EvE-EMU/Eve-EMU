import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EvE-EMU",
  description:
    "Industrial, PvP, and automation suite for EVE Online organizations — Discord-first workflows with FastAPI core and optional Alliance Auth.",
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
