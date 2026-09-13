"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  type AuthSession,
  normalizeAccessLevel,
  type AccessLevel,
} from "@/lib/permissions";

export type LinkedAlt = {
  character_id: number;
  character_name: string;
  is_main?: boolean;
  token_valid?: boolean;
};

type AuthContextValue = {
  session: AuthSession;
  loading: boolean;
  switching: boolean;
  switchError: string | null;
  ssoError: string | null;
  ssoSuccess: string | null;
  refresh: () => Promise<void>;
  switchCharacter: (characterId: number) => Promise<boolean>;
  linkAltUrl: string;
  clearSsoNotice: () => void;
};

const PUBLIC_SESSION: AuthSession = {
  authenticated: false,
  character_id: null,
  character_name: null,
  state: null,
  access_level: "public",
  permissions: ["tools.public"],
  login_url: "/api/auth/sso/login",
  reauthorize_url: "/api/auth/sso/login",
  token_valid: false,
  alts: [],
  hr_lookup: false,
};

const AuthContext = createContext<AuthContextValue>({
  session: PUBLIC_SESSION,
  loading: true,
  switching: false,
  switchError: null,
  ssoError: null,
  ssoSuccess: null,
  refresh: async () => undefined,
  switchCharacter: async () => false,
  linkAltUrl: "/api/auth/sso/link",
  clearSsoNotice: () => undefined,
});

function parseAlts(raw: unknown): LinkedAlt[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const r = row as Record<string, unknown>;
      const character_id = typeof r.character_id === "number" ? r.character_id : null;
      if (!character_id) return null;
      return {
        character_id,
        character_name: typeof r.character_name === "string" ? r.character_name : `Pilot ${character_id}`,
        is_main: Boolean(r.is_main),
        token_valid: r.token_valid !== false,
      };
    })
    .filter(Boolean) as LinkedAlt[];
}

function parseSession(data: Record<string, unknown>): AuthSession {
  const authenticated = Boolean(data.authenticated);
  const state = typeof data.state === "string" ? data.state : null;
  const accessLevel =
    (typeof data.access_level === "string" ? data.access_level : null) as AccessLevel | null;
  const permissions = Array.isArray(data.permissions)
    ? data.permissions.map(String)
    : authenticated
      ? ["tools.guest"]
      : ["tools.public"];

  const authNoticeRaw = data.auth_notice;
  const auth_notice =
    authNoticeRaw === "reauthorize" || authNoticeRaw === "missing_scopes" ? authNoticeRaw : null;

  return {
    authenticated,
    character_id: typeof data.character_id === "number" ? data.character_id : null,
    character_name: typeof data.character_name === "string" ? data.character_name : null,
    corporation_name: typeof data.corporation_name === "string" ? data.corporation_name : null,
    alliance_name: typeof data.alliance_name === "string" ? data.alliance_name : null,
    state,
    access_level: accessLevel ?? normalizeAccessLevel(state, authenticated),
    state_color: typeof data.state_color === "string" ? data.state_color : null,
    permissions,
    login_url: typeof data.login_url === "string" ? data.login_url : "/api/auth/sso/login",
    link_alt_url: typeof data.link_alt_url === "string" ? data.link_alt_url : "/api/auth/sso/link",
    reauthorize_url:
      typeof data.reauthorize_url === "string" ? data.reauthorize_url : "/api/auth/sso/login",
    hr_lookup: Boolean(data.hr_lookup),
    token_valid: data.token_valid !== false,
    auth_notice,
    missing_scope_count:
      typeof data.missing_scope_count === "number" ? data.missing_scope_count : undefined,
    missing_scopes: Array.isArray(data.missing_scopes)
      ? data.missing_scopes.map(String)
      : undefined,
    alts: parseAlts(data.alts),
  };
}

function readUrlNotices(): { error: string | null; success: string | null } {
  if (typeof window === "undefined") return { error: null, success: null };
  const params = new URLSearchParams(window.location.search);
  const error = params.get("sso_error");
  const success = params.get("alt_linked") === "1" ? "alt_linked" : null;
  if (error || success) {
    const url = new URL(window.location.href);
    url.searchParams.delete("sso_error");
    url.searchParams.delete("alt_linked");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }
  return { error, success };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession>(PUBLIC_SESSION);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [ssoError, setSsoError] = useState<string | null>(null);
  const [ssoSuccess, setSsoSuccess] = useState<string | null>(null);

  const clearSsoNotice = useCallback(() => {
    setSsoError(null);
    setSsoSuccess(null);
    setSwitchError(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
      if (res.ok) {
        setSession(parseSession(await res.json()));
      } else {
        setSession(PUBLIC_SESSION);
      }
    } catch {
      setSession(PUBLIC_SESSION);
    } finally {
      setLoading(false);
    }
  }, []);

  const switchCharacter = useCallback(
    async (characterId: number) => {
      if (switching) return false;
      setSwitching(true);
      setSwitchError(null);
      try {
        const res = await fetch("/api/auth/switch", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ character_id: characterId }),
        });
        if (!res.ok) {
          let message = "Could not switch pilot.";
          try {
            const body = (await res.json()) as { detail?: string };
            if (body.detail) message = body.detail;
          } catch {
            /* ignore */
          }
          setSwitchError(message);
          return false;
        }
        await refresh();
        window.dispatchEvent(
          new CustomEvent("emums:character-switch", { detail: { character_id: characterId } })
        );
        return true;
      } catch {
        setSwitchError("Could not switch pilot — network error.");
        return false;
      } finally {
        setSwitching(false);
      }
    },
    [refresh, switching]
  );

  useEffect(() => {
    const notices = readUrlNotices();
    if (notices.error) setSsoError(notices.error);
    if (notices.success) setSsoSuccess(notices.success);
    void refresh();
    if (notices.success === "alt_linked") {
      window.dispatchEvent(new CustomEvent("emums:roster-updated"));
    }
  }, [refresh]);

  const value = useMemo(
    () => ({
      session,
      loading,
      switching,
      switchError,
      ssoError,
      ssoSuccess,
      refresh,
      switchCharacter,
      linkAltUrl: session.link_alt_url || "/api/auth/sso/link",
      clearSsoNotice,
    }),
    [session, loading, switching, switchError, ssoError, ssoSuccess, refresh, switchCharacter, clearSsoNotice]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
