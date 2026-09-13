"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { ssoErrorMessage } from "@/lib/ssoMessages";

export function SsoNoticeBanner() {
  const { session, ssoError, ssoSuccess, clearSsoNotice } = useAuth();

  if (ssoError) {
    return (
      <div className="eve-sso-notice eve-sso-notice--error" role="alert">
        <span>{ssoErrorMessage(ssoError) ?? "Login failed."}</span>
        <Link href={session.login_url || "/api/auth/sso/login"} className="eve-sso-notice-action">
          Try again
        </Link>
        <button type="button" className="eve-sso-notice-dismiss" onClick={clearSsoNotice} aria-label="Dismiss">
          ×
        </button>
      </div>
    );
  }

  if (ssoSuccess === "alt_linked") {
    return (
      <div className="eve-sso-notice eve-sso-notice--ok" role="status">
        <span>Alt linked successfully — select it in the pilot roster to switch.</span>
        <button type="button" className="eve-sso-notice-dismiss" onClick={clearSsoNotice} aria-label="Dismiss">
          ×
        </button>
      </div>
    );
  }

  if (session.authenticated && session.auth_notice === "reauthorize") {
    return (
      <div className="eve-sso-notice eve-sso-notice--warn" role="alert">
        <span>
          ESI token for <strong>{session.character_name}</strong> expired — re-authorize to use audit and market tools.
        </span>
        <Link href={session.reauthorize_url || "/api/auth/sso/login"} className="eve-sso-notice-action">
          Re-authorize SSO
        </Link>
      </div>
    );
  }

  if (
    session.authenticated &&
    session.auth_notice === "missing_scopes" &&
    (session.missing_scope_count ?? 0) > 0
  ) {
    return (
      <div className="eve-sso-notice eve-sso-notice--warn" role="status">
        <span>
          {session.missing_scope_count} ESI scope{session.missing_scope_count === 1 ? "" : "s"} missing — some tools
          may fail until you re-login and grant full access.
        </span>
        <Link href={session.reauthorize_url || "/api/auth/sso/login"} className="eve-sso-notice-action">
          Update scopes
        </Link>
      </div>
    );
  }

  return null;
}
