"use client";

import Link from "next/link";
import { ACCESS_STATE_META, PERMISSION_MODULES, type AccessLevel } from "@/lib/permissions";
import { useAuth } from "./AuthProvider";

const PUBLIC_TOOL_LINKS = [
  { href: "/sde", label: "SDE & Wiki browser" },
  { href: "/map", label: "Map & jump planner" },
  { href: "/commerce", label: "Buyback & appraisal" },
];

export function AccessGate({ requiredModule }: { requiredModule: string }) {
  const { session } = useAuth();
  const mod = PERMISSION_MODULES.find((m) => m.id === requiredModule);
  const minLevel = (mod?.minLevel ?? "guest") as AccessLevel;
  const levelMeta = ACCESS_STATE_META[minLevel];

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center p-4">
      <div className="eve-access-gate max-w-lg w-full">
        <div className="eve-window-titlebar">
          <span className="eve-window-title">Authentication required</span>
        </div>
        <div className="eve-window-body space-y-3 text-[11px]">
          <p className="text-[var(--text-muted)] leading-relaxed">
            Coalition tools on EMUMS require an authenticated EVE Online character
            {mod ? (
              <>
                {" "}
                with <span className={`eve-state-pill ${levelMeta.cssClass}`}>{levelMeta.label}</span> access or
                higher.
              </>
            ) : (
              "."
            )}
          </p>
          {mod ? <p className="text-[10px] text-[var(--text-dim)]">{mod.description}</p> : null}
          <div className="flex flex-wrap gap-2 pt-1">
            <Link href={session.login_url || "/api/auth/sso/login"} className="eve-btn eve-btn-primary">
              Login with EVE SSO
            </Link>
          </div>
          <div className="border-t border-[var(--edge-dim)] pt-3">
            <p className="text-[10px] text-[var(--text-muted)] mb-2">Public tools — no login required</p>
            <ul className="space-y-1">
              {PUBLIC_TOOL_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-[var(--link)] hover:text-[var(--link-hi)]">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
