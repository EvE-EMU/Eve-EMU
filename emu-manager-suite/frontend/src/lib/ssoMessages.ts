/** User-facing SSO / session status messages. */

export const SSO_ERROR_MESSAGES: Record<string, string> = {
  access_denied: "EVE SSO login was cancelled.",
  missing_code: "Login callback missing authorization code — try again.",
  no_session: "Login completed but no session was created — try again.",
  exchange_failed: "Could not complete EVE SSO login — try again.",
  state_expired: "Login session expired — click Login and complete SSO within 15 minutes.",
  login_unavailable: "EVE SSO is not configured on this server — contact admins.",
  link_unavailable: "Alt linking unavailable — log in first, then try again.",
  server_error: "Login server error — try again in a moment.",
};

export function ssoErrorMessage(code: string | null | undefined): string | null {
  if (!code) return null;
  const key = code.toLowerCase();
  if (SSO_ERROR_MESSAGES[key]) return SSO_ERROR_MESSAGES[key];
  if (key.includes("invalid") && key.includes("state")) {
    return SSO_ERROR_MESSAGES.state_expired;
  }
  return `Login failed (${code}). Try again or contact support.`;
}

export function mapExchangeDetail(detail: string): string {
  const lower = detail.toLowerCase();
  if (lower.includes("invalid or expired sso state")) return "state_expired";
  if (lower.includes("missing tokens")) return "exchange_failed";
  if (lower.includes("not configured")) return "login_unavailable";
  if (lower.includes("token exchange failed")) return "exchange_failed";
  return "exchange_failed";
}
