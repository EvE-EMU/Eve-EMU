"use client";

import clsx from "clsx";
import Link from "next/link";
import { ACCESS_STATE_META } from "@/lib/permissions";
import { useAuth } from "./AuthProvider";
import { AltManager } from "./AltManager";
import { Tooltip } from "./Tooltip";
import {
  UI_SCALE_MAX,
  UI_SCALE_MIN,
  UI_SCALE_STEP,
  uiScalePercent,
  useDisplayPreferences,
} from "./DisplayPreferencesProvider";

function IconEveLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 1.2 1.5 5v6L8 14.8 14.5 11V5L8 1.2zm0 1.4 5.2 2.9v5.4L8 13.8l-5.2-2.9V5.5L8 2.6z" />
    </svg>
  );
}

function DisplayQuickControls() {
  const { prefs, bumpUiScale } = useDisplayPreferences();
  const zoomLabel = `${uiScalePercent(prefs.uiScale)}%`;

  return (
    <div className="eve-display-quick" title="UI scale — open Settings → Display & Zoom for more">
      <button
        type="button"
        className="eve-display-quick-btn"
        aria-label="Decrease UI size"
        disabled={prefs.uiScale <= UI_SCALE_MIN}
        onClick={() => bumpUiScale(-UI_SCALE_STEP)}
      >
        A−
      </button>
      <span className="eve-display-quick-label">{zoomLabel}</span>
      <button
        type="button"
        className="eve-display-quick-btn"
        aria-label="Increase UI size"
        disabled={prefs.uiScale >= UI_SCALE_MAX}
        onClick={() => bumpUiScale(UI_SCALE_STEP)}
      >
        A+
      </button>
    </div>
  );
}

export function SessionControls() {
  const { session, loading } = useAuth();
  const meta = ACCESS_STATE_META[session.access_level];

  if (loading) {
    return <span className="eve-session-loading text-[10px] text-[var(--text-muted)]">Session…</span>;
  }

  if (!session.authenticated) {
    return (
      <div className="eve-session-controls">
        <DisplayQuickControls />
        <Tooltip label="EVE SSO" hint="Log in with your EVE Online character to unlock coalition tools" side="bottom">
          <Link href={session.login_url || "/api/auth/sso/login"} className="eve-sso-btn">
            <IconEveLogo className="h-3.5 w-3.5" />
            <span>Login with EVE SSO</span>
          </Link>
        </Tooltip>
      </div>
    );
  }

  return (
    <div className="eve-session-controls">
      <DisplayQuickControls />
      <AltManager />
      <span className={clsx("eve-state-pill", meta.cssClass)} title={meta.description}>
        {session.state || meta.label}
      </span>
      <Tooltip
        label={session.character_name || "Pilot"}
        hint={[session.corporation_name, session.alliance_name].filter(Boolean).join(" · ") || "Authenticated"}
        side="bottom"
      >
        <span className="eve-session-pilot truncate max-w-[140px]">{session.character_name}</span>
      </Tooltip>
    </div>
  );
}
