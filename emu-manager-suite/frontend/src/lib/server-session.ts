import { cookies } from "next/headers";
import { EMUMS_API_KEY, EMUMS_API_URL } from "@/lib/bff";
import type { AuthSession } from "@/lib/permissions";
import { normalizeAccessLevel } from "@/lib/permissions";

export async function fetchServerSession(): Promise<AuthSession | null> {
  const cookieStore = await cookies();
  const session = cookieStore.get("emums_session")?.value;
  const res = await fetch(`${EMUMS_API_URL}/auth/me`, {
    headers: {
      "X-EMUMS-Key": EMUMS_API_KEY,
      ...(session ? { "X-EMUMS-Session": session } : {}),
    },
    cache: "no-store",
  });
  if (!res.ok) return null;
  const data = await res.json();
  const authenticated = Boolean(data.authenticated);
  return {
    authenticated,
    character_id: data.character_id ?? null,
    character_name: data.character_name ?? null,
    corporation_name: data.corporation_name ?? null,
    alliance_name: data.alliance_name ?? null,
    state: data.state ?? null,
    access_level: data.access_level ?? normalizeAccessLevel(data.state, authenticated),
    state_color: data.state_color ?? null,
    permissions: Array.isArray(data.permissions) ? data.permissions.map(String) : ["tools.public"],
    login_url: data.login_url ?? "/api/auth/sso/login",
    reauthorize_url: data.reauthorize_url ?? "/api/auth/sso/login",
    token_valid: data.token_valid !== false,
    auth_notice:
      data.auth_notice === "reauthorize" || data.auth_notice === "missing_scopes"
        ? data.auth_notice
        : null,
    missing_scope_count:
      typeof data.missing_scope_count === "number" ? data.missing_scope_count : undefined,
  };
}
