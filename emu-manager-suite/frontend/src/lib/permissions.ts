/** Coalition access levels and permission modules (Alliance Auth–style). */

export type AccessLevel = "public" | "guest" | "friendly" | "blue" | "member" | "red";

export type PermissionModule = {
  id: string;
  label: string;
  description: string;
  minLevel: AccessLevel;
  permissions: string[];
  blocked?: boolean;
};

export type AuthSession = {
  authenticated: boolean;
  character_id: number | null;
  character_name: string | null;
  corporation_name?: string | null;
  alliance_name?: string | null;
  state: string | null;
  access_level: AccessLevel;
  state_color?: string | null;
  permissions: string[];
  login_url?: string;
  link_alt_url?: string;
  hr_lookup?: boolean;
  token_valid?: boolean;
  auth_notice?: "reauthorize" | "missing_scopes" | null;
  reauthorize_url?: string;
  missing_scope_count?: number;
  missing_scopes?: string[];
  alts?: {
    character_id: number;
    character_name: string;
    is_main?: boolean;
    token_valid?: boolean;
  }[];
};

export const ACCESS_LEVEL_ORDER: AccessLevel[] = [
  "public",
  "red",
  "guest",
  "friendly",
  "blue",
  "member",
];

export const ACCESS_STATE_META: Record<
  AccessLevel,
  { label: string; color: string; cssClass: string; description: string }
> = {
  public: {
    label: "Public",
    color: "gray",
    cssClass: "eve-state-public",
    description: "Unauthenticated visitor — public tools only",
  },
  guest: {
    label: "Guest",
    color: "gray",
    cssClass: "eve-state-guest",
    description: "Logged-in pilot without coalition standing",
  },
  friendly: {
    label: "Friendly",
    color: "teal",
    cssClass: "eve-state-friendly",
    description: "Friendly standings — limited coalition tools",
  },
  blue: {
    label: "Blue",
    color: "blue",
    cssClass: "eve-state-blue",
    description: "Coalition blue — allied access tier",
  },
  member: {
    label: "Member",
    color: "green",
    cssClass: "eve-state-member",
    description: "Full coalition member access",
  },
  red: {
    label: "Red",
    color: "red",
    cssClass: "eve-state-red",
    description: "Hostile — restricted to public surfaces",
  },
};

export const PERMISSION_MODULES: PermissionModule[] = [
  {
    id: "public",
    label: "Public",
    description: "Buyback, appraisal, SDE browser, map planner — no login required",
    minLevel: "public",
    permissions: ["tools.public"],
  },
  {
    id: "guest",
    label: "Guest",
    description: "Authenticated pilots — bookmarks, personal route saves",
    minLevel: "guest",
    permissions: ["tools.guest", "map.bookmarks"],
  },
  {
    id: "friendly",
    label: "Friendly",
    description: "Friendly standings — intel read-only and shared market views",
    minLevel: "friendly",
    permissions: ["tools.friendly", "intel.read"],
  },
  {
    id: "blue",
    label: "Blue",
    description: "Coalition blues — industrial storefront and corp market",
    minLevel: "blue",
    permissions: ["tools.blue", "industrial.storefront"],
  },
  {
    id: "member",
    label: "Member",
    description: "Coalition members — moons, HR, SRP, full hub",
    minLevel: "member",
    permissions: ["tools.member", "industrial.storefront", "moons.view", "hr.view", "srp.submit"],
  },
  {
    id: "director",
    label: "Directorate",
    description: "Directors — administration, audit, identity, tax configuration",
    minLevel: "member",
    permissions: ["director", "settings.admin", "audit.view"],
  },
  {
    id: "red",
    label: "Red",
    description: "Hostile flag — blocks coalition tools",
    minLevel: "public",
    permissions: ["state.red"],
    blocked: true,
  },
];

const LEVEL_RANK: Record<AccessLevel, number> = {
  public: 0,
  red: 0,
  guest: 10,
  friendly: 20,
  blue: 30,
  member: 50,
};

export function normalizeAccessLevel(state: string | null | undefined, authenticated: boolean): AccessLevel {
  if (!authenticated) return "public";
  if (!state) return "guest";
  const key = state.toLowerCase().replace(/\s+/g, "_") as AccessLevel;
  if (key in ACCESS_STATE_META) return key;
  return "guest";
}

export function levelRank(level: AccessLevel): number {
  return LEVEL_RANK[level] ?? 0;
}

export function isRedFlagged(session: AuthSession): boolean {
  return session.access_level === "red" || session.permissions.includes("state.red");
}

export function hasPermission(session: AuthSession, perm: string): boolean {
  if (session.permissions.includes("director") || session.permissions.includes("admin")) return true;
  return session.permissions.includes(perm);
}

/** Coalition administrators — Directors group or explicit settings.admin grant. */
export function isAdministrator(session: AuthSession): boolean {
  if (!session.authenticated) return false;
  return (
    hasPermission(session, "director") ||
    hasPermission(session, "admin") ||
    hasPermission(session, "settings.admin")
  );
}

export function canAccessModule(session: AuthSession, moduleId: string): boolean {
  if (moduleId === "administrator") return isAdministrator(session);
  const mod = PERMISSION_MODULES.find((m) => m.id === moduleId);
  if (!mod) return true;
  if (mod.blocked) return isRedFlagged(session);
  if (mod.minLevel !== "public" && !session.authenticated) return false;
  if (isRedFlagged(session) && mod.minLevel !== "public") return false;
  return levelRank(session.access_level) >= levelRank(mod.minLevel);
}

export function canAccessRoute(session: AuthSession, requiredModule?: string): boolean {
  if (!requiredModule || requiredModule === "public") return true;
  return canAccessModule(session, requiredModule);
}

/** Map nav sections to minimum permission module. */
export const ROUTE_ACCESS: Record<string, string> = {
  "/": "public",
  activities: "member",
  finance: "guest",
  industry: "blue",
  inventory: "blue",
  personal: "guest",
  ship: "public",
  social: "member",
  "emu-services": "member",
  utilities: "public",
  settings: "guest",
  "/sde": "public",
  "/map": "public",
  "/commerce": "public",
  "/hub": "guest",
  "/industrial": "blue",
  "/moons": "member",
  "/intelligence": "friendly",
  "/administration": "director",
  "/templates": "member",
  "/operations": "blue",
};

/** Resolve required module for a pathname (longest prefix wins). */
export function resolveRouteModule(pathname: string): string {
  if (ROUTE_ACCESS[pathname]) return ROUTE_ACCESS[pathname];
  const sorted = Object.entries(ROUTE_ACCESS).sort((a, b) => b[0].length - a[0].length);
  for (const [path, moduleId] of sorted) {
    if (path === "/") continue;
    if (pathname === path || pathname.startsWith(`${path}/`)) return moduleId;
  }
  return "guest";
}
