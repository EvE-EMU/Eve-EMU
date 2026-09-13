"use client";

import { Neocom, NeocomLocationTitle } from "./Neocom";
import { WindowManagerProvider } from "./WindowManager";
import { AuthProvider } from "./AuthProvider";
import { SsoNoticeBanner } from "./SsoNoticeBanner";
import { DisplayPreferencesProvider } from "./DisplayPreferencesProvider";
import { DesktopVideoBackground } from "./DesktopVideoBackground";
import { NotificationProvider } from "./notifications/NotificationProvider";
import { NotificationBell } from "./notifications/NotificationBell";
import { AppFooter, GlobalSearch } from "./GlobalSearch";
import { RouteGuard } from "./RouteGuard";
import { SessionControls } from "./SessionControls";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <DisplayPreferencesProvider>
        <NotificationProvider>
          <WindowManagerProvider>
          <div className="eve-app-bg min-h-screen flex">
            <Neocom />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <header className="eve-location-bar">
                <div className="min-w-0 truncate flex items-center gap-3">
                  <NeocomLocationTitle />
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <GlobalSearch />
                  <SessionControls />
                  <span className="hidden xl:inline text-[var(--text-muted)]">EvE EMU | Edging Gone Wild</span>
                </div>
              </header>

              <SsoNoticeBanner />

              <main className="eve-main flex-1 min-h-0 overflow-hidden p-1.5 md:p-2">
                <DesktopVideoBackground />
                <div className="eve-main-content">
                  <RouteGuard>{children}</RouteGuard>
                </div>
              </main>

              <div className="eve-notify-strip">
                <NotificationBell />
              </div>

              <AppFooter />
            </div>
          </div>
        </WindowManagerProvider>
      </NotificationProvider>
      </DisplayPreferencesProvider>
    </AuthProvider>
  );
}
