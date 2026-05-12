import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EVE-EMU Core",
  description: "Main web app for EVE-EMU (Discord bot is a separate surface).",
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
