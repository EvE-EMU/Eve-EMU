/** EVE-client-style neocom sections and launchable windows. */

import type { AuthSession } from "@/lib/permissions";
import { canAccessModule } from "@/lib/permissions";

export type NavSectionId =
  | "activities"
  | "finance"
  | "industry"
  | "inventory"
  | "personal"
  | "ship"
  | "social"
  | "emu-services"
  | "utilities"
  | "settings";

/** Visual groupings in the icon rail — matches EVE neocom clusters. */
export const NEOCOM_NAV_GROUPS: { sections: NavSectionId[] }[] = [
  { sections: ["activities", "finance", "industry", "inventory"] },
  { sections: ["personal", "ship"] },
  { sections: ["social", "emu-services"] },
  { sections: ["utilities", "settings"] },
];

export type NavWindowEntry = {
  windowId: string;
  label: string;
  /** URL ?tool= slug when opening from submenu */
  slug?: string;
  /** Permission module override (defaults to section module) */
  module?: string;
  public?: boolean;
  /** Sidebar group label within the neocom panel (e.g. Administrator) */
  sidebar?: string;
};

export type NavSection = {
  id: NavSectionId;
  label: string;
  tip: string;
  module: string;
  defaultWindow: string;
  windows: NavWindowEntry[];
  /** Append registered template-* windows to the submenu */
  includeTemplateWindows?: boolean;
};

export const NEOCOM_SECTIONS: NavSection[] = [
  {
    id: "activities",
    label: "Activities",
    tip: "Mining, ratting, SRP, and ops dashboards",
    module: "member",
    defaultWindow: "killboard",
    windows: [
      { windowId: "killboard", label: "Killboard", slug: "killboard", module: "friendly" },
      { windowId: "srp-program", label: "SRP Program", slug: "srp", module: "member" },
      { windowId: "ratting-tax", label: "Ratting Tax", slug: "ratting", module: "member" },
      { windowId: "moon-productivity", label: "Moon Productivity", module: "member" },
      { windowId: "moon-timing", label: "Moon Mining Timing", module: "member" },
      { windowId: "nationalized-inspector", label: "Nationalized Inspector", module: "member" },
      { windowId: "observer-log", label: "Observer Log", module: "member" },
      { windowId: "extraction-volume", label: "Extraction Volume", module: "member" },
      { windowId: "rarity-mix", label: "Rarity Mix", module: "member" },
      { windowId: "structure-output", label: "Structure Output", module: "member" },
    ],
  },
  {
    id: "finance",
    label: "Finance",
    tip: "Buyback, markets, and invoices",
    module: "guest",
    defaultWindow: "buyback",
    windows: [
      { windowId: "buyback", label: "Buyback", slug: "buyback", public: true },
      { windowId: "appraisal", label: "Appraisal", slug: "appraisal", public: true },
      { windowId: "refine-calc", label: "Refine vs Sell", slug: "refine", public: true },
      { windowId: "market-watch", label: "Market Tracker", slug: "market", module: "guest" },
      { windowId: "market-browser", label: "Market Browser", slug: "market-browser", public: true },
      { windowId: "market-stations", label: "NPC Stations", module: "guest" },
      { windowId: "corp-market", label: "Corp Market", slug: "corp-market", module: "blue" },
      { windowId: "pni-statements", label: "P&I Statements", slug: "pni", module: "member" },
      { windowId: "invoice-status", label: "Invoice Status", module: "member" },
      { windowId: "recent-tax", label: "Recent Tax Assessments", module: "member" },
      { windowId: "ip-projects", label: "Project Costing", slug: "ip-projects", module: "blue" },
    ],
  },
  {
    id: "industry",
    label: "Industry",
    tip: "Canonical industrial suite: eve-emu.com/industrial",
    module: "blue",
    defaultWindow: "ip-planner",
    windows: [
      { windowId: "pi-overview", label: "Planetary Interaction", slug: "pi", module: "guest" },
      { windowId: "ip-planner", label: "Build Planner (legacy)", slug: "ip-planner" },
      { windowId: "ip-blueprints", label: "Blueprints & Contracts", slug: "ip-blueprints" },
      { windowId: "ip-jobs", label: "Industry Jobs", slug: "ip-jobs" },
      { windowId: "ip-storefront", label: "Storefront", slug: "ip-storefront", public: true },
    ],
  },
  {
    id: "inventory",
    label: "Inventory",
    tip: "Structures, markets, and asset views",
    module: "blue",
    defaultWindow: "authed-structures",
    windows: [
      { windowId: "authed-structures", label: "Authed Structures", module: "guest" },
      { windowId: "structure-fuel", label: "Structure Fuel", module: "member" },
      { windowId: "corp-market", label: "Corp Market", slug: "corp-market" },
      { windowId: "market-browser", label: "Market Browser", slug: "market-browser", public: true },
      { windowId: "ip-storefront", label: "Storefront", slug: "ip-storefront", public: true },
    ],
  },
  {
    id: "personal",
    label: "Personal",
    tip: "Character sheet, skills, wallet, and assets",
    module: "guest",
    defaultWindow: "char-audit",
    windows: [
      { windowId: "char-audit", label: "Character Audit", slug: "audit", module: "guest" },
      { windowId: "interaction-audit", label: "Interaction Audit", slug: "interactions", module: "guest" },
      { windowId: "webhook-alerts", label: "Webhook Alerts", slug: "webhook-alerts", module: "guest" },
    ],
  },
  {
    id: "ship",
    label: "Ship",
    tip: "Fittings, routes, and jump planning",
    module: "public",
    defaultWindow: "map-visual",
    windows: [
      { windowId: "map-visual", label: "Route Map", slug: "map", public: true },
      { windowId: "route-planner", label: "Route Bookmarks", slug: "routes", module: "guest" },
      { windowId: "map-planner", label: "Route Planner", module: "guest" },
    ],
  },
  {
    id: "social",
    label: "Social",
    tip: "HR, onboarding, standings, calendar, and templates",
    module: "member",
    defaultWindow: "onboarding",
    includeTemplateWindows: true,
    windows: [
      { windowId: "onboarding", label: "Onboarding Manager", slug: "onboarding", module: "guest" },
      { windowId: "admission-rank", label: "Admission Ranking", slug: "admission", module: "guest" },
      { windowId: "standings-sync", label: "Standings Sync", slug: "standings", module: "guest" },
      { windowId: "ops-calendar", label: "Operations Calendar", slug: "calendar", module: "guest" },
      { windowId: "hr-directorate", label: "HR Directorate", slug: "hr", module: "member" },
      { windowId: "services", label: "Service Links", slug: "services", module: "member" },
    ],
  },

  {
    id: "emu-services",
    label: "EMU Services",
    tip: "Coalition hub, infrastructure, and administration",
    module: "member",
    defaultWindow: "tools-hub",
    windows: [
      { windowId: "tools-hub", label: "Coalition Tool Hub", module: "guest" },
      { windowId: "admin-infra", label: "Infrastructure", slug: "infra", module: "director" },
      { windowId: "identity-rbac", label: "Permissions Manager", slug: "identity-rbac", module: "director" },

      { windowId: "admin-audit", label: "Security Audit", slug: "security-audit", module: "director" },
    ],
  },
  {
    id: "utilities",
    label: "Utilities",
    tip: "Awesome-eve suite, knowledge, and reference tools",
    module: "public",
    defaultWindow: "suite-hub",
    windows: [
      { windowId: "suite-hub", label: "Awesome Tool Suite", slug: "suite", public: true },
      { windowId: "suite-intel", label: "Intel Paste", public: true },
      { windowId: "suite-trade", label: "Trade Margins", public: true },
      { windowId: "suite-corpwho", label: "Corp Who", public: true },
      { windowId: "suite-br", label: "Battle Report", public: true },
      { windowId: "suite-skills", label: "Skill Queues", module: "guest" },
      { windowId: "suite-gatecamp", label: "Gate Camp Route", public: true },
      { windowId: "suite-haul", label: "Haul Finder", public: true },
      { windowId: "suite-structures", label: "Structure Board", public: true },
      { windowId: "suite-ships", label: "Ship Compare", public: true },
      { windowId: "suite-insurance", label: "Insurance Check", public: true },
      { windowId: "about", label: "About EMUMS", public: true },
      { windowId: "sde-browser", label: "Knowledge & SDE", slug: "sde", public: true },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    tip: "Display preferences and administrator configuration",
    module: "guest",
    defaultWindow: "display-settings",
    windows: [
      { windowId: "display-settings", label: "Display & Zoom", public: true },
      {
        windowId: "org-settings",
        label: "Org Settings",
        module: "administrator",
        sidebar: "Administrator",
      },
      {
        windowId: "ops-tagline",
        label: "Ops Tagline",
        module: "administrator",
        sidebar: "Administrator",
      },
      {
        windowId: "moon-tax",
        label: "Moon Tax Config",
        slug: "moon-tax-admin",
        module: "administrator",
        sidebar: "Administrator",
      },
      {
        windowId: "admin-users",
        label: "Users & Permissions",
        module: "administrator",
        sidebar: "Administrator",
      },
    ],
  },
];

export const NAV_LAUNCH_WINDOWS: Record<string, string> = Object.fromEntries(
  NEOCOM_SECTIONS.map((s) => [s.id, s.defaultWindow])
);

export const WINDOW_NAV_SECTION: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  for (const section of NEOCOM_SECTIONS) {
    for (const win of section.windows) {
      map[win.windowId] = section.id;
    }
  }
  map["char-item-detail"] = "personal";
  map["char-ship-fitting"] = "ship";
  map["char-system-detail"] = "personal";
  map["char-org-wiki"] = "social";
  map["sde-detail"] = "utilities";
  map["sde-compare"] = "utilities";
  map["wiki-article"] = "utilities";
  map["wh-map"] = "ship";
  map["about"] = "utilities";
  map["suite-hub"] = "utilities";
  map["suite-intel"] = "utilities";
  map["suite-trade"] = "utilities";
  map["suite-corpwho"] = "utilities";
  map["suite-br"] = "utilities";
  map["suite-skills"] = "utilities";
  map["suite-gatecamp"] = "utilities";
  map["suite-haul"] = "utilities";
  map["suite-structures"] = "utilities";
  map["suite-ships"] = "utilities";
  map["suite-insurance"] = "utilities";
  map["structure-fuel"] = "inventory";
  map["moon-timing"] = "activities";
  return map;
})();

export function getNavSection(id: string): NavSection | undefined {
  return NEOCOM_SECTIONS.find((s) => s.id === id);
}

export function canOpenNavWindow(session: AuthSession, entry: NavWindowEntry, section: NavSection): boolean {
  if (entry.public) return true;
  const moduleId = entry.module ?? section.module;
  return canAccessModule(session, moduleId);
}

export function windowsForSection(
  sectionId: string,
  session: AuthSession,
  registeredWindowIds: Set<string>
): { windowId: string; label: string; slug?: string; sidebar?: string }[] {
  const section = getNavSection(sectionId);
  if (!section) return [];

  const seen = new Set<string>();
  const items: { windowId: string; label: string; slug?: string; sidebar?: string }[] = [];

  for (const entry of section.windows) {
    if (seen.has(entry.windowId)) continue;
    if (!canOpenNavWindow(session, entry, section)) continue;
    seen.add(entry.windowId);
    items.push({
      windowId: entry.windowId,
      label: entry.label,
      slug: entry.slug,
      sidebar: entry.sidebar,
    });
  }

  if (section.includeTemplateWindows) {
    for (const id of registeredWindowIds) {
      if (!id.startsWith("template-")) continue;
      if (seen.has(id)) continue;
      seen.add(id);
      const slug = id.slice("template-".length);
      const label = slug
        .split("-")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
      items.push({ windowId: id, label: `Template: ${label}` });
    }
  }

  return items;
}

/** Open/minimized/maximized windows belonging to a neocom section. */
export function countSectionOpenWindows(
  sectionId: string,
  windows: { id: string; mode: string }[]
): number {
  return windows.filter((w) => {
    if (w.mode === "closed") return false;
    const sec = WINDOW_NAV_SECTION[w.id];
    if (sec === sectionId) return true;
    if (sectionId === "social" && w.id.startsWith("template-")) return true;
    return false;
  }).length;
}

export function sortNavMenuItems<T extends { windowId: string; label: string }>(
  items: T[],
  windows: { id: string; mode: string }[]
): T[] {
  const modeById = new Map(windows.map((w) => [w.id, w.mode]));
  return [...items].sort((a, b) => {
    const aOpen = modeById.get(a.windowId) !== undefined && modeById.get(a.windowId) !== "closed";
    const bOpen = modeById.get(b.windowId) !== undefined && modeById.get(b.windowId) !== "closed";
    if (aOpen !== bOpen) return aOpen ? -1 : 1;
    return a.label.localeCompare(b.label);
  });
}

/** Group neocom menu items by optional sidebar label (null = ungrouped first). */
export function groupNavMenuItems<T extends { sidebar?: string }>(
  items: T[]
): { label: string | null; items: T[] }[] {
  const general: T[] = [];
  const bySidebar = new Map<string, T[]>();
  for (const item of items) {
    const key = item.sidebar?.trim();
    if (!key) {
      general.push(item);
      continue;
    }
    const list = bySidebar.get(key) ?? [];
    list.push(item);
    bySidebar.set(key, list);
  }
  const groups: { label: string | null; items: T[] }[] = [];
  if (general.length) groups.push({ label: null, items: general });
  for (const [label, groupItems] of [...bySidebar.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    groups.push({ label, items: groupItems });
  }
  return groups;
}
