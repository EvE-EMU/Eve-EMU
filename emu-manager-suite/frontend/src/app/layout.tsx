import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/AppShell";
import { displayPrefsBootScript } from "@/lib/displayPreferences";
import "./globals.css";

export const metadata: Metadata = {
  title: "EMU Manager Suite",
  description: "EVE-style operations suite — emums.eve-emu.com",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d1014",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://images.evetech.net" crossOrigin="anonymous" />
        <script dangerouslySetInnerHTML={{ __html: displayPrefsBootScript() }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
