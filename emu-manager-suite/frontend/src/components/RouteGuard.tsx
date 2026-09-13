"use client";

import { usePathname } from "next/navigation";
import { canAccessRoute, resolveRouteModule } from "@/lib/permissions";
import { useAuth } from "./AuthProvider";
import { AccessGate } from "./AccessGate";

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { session, loading } = useAuth();
  const requiredModule = resolveRouteModule(path);
  const allowed = canAccessRoute(session, requiredModule);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-[11px] text-[var(--text-muted)]">
        Verifying session…
      </div>
    );
  }

  if (!allowed) {
    return <AccessGate requiredModule={requiredModule} />;
  }

  return <>{children}</>;
}
