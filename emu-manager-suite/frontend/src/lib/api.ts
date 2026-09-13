/** Server-side API client — key never sent to browser. */

import { EMUMS_API_KEY, EMUMS_API_URL } from "@/lib/bff";

async function emumsFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${EMUMS_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-EMUMS-Key": EMUMS_API_KEY,
      ...(init?.headers || {}),
    },
    next: { revalidate: 30 },
  });
  if (!res.ok) {
    throw new Error(`EMUMS API ${path}: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type Dashboard = {
  tagline: string;
  kpis: { label: string; value: string; tone: string }[];
  mining_by_day: { date: string; volume: number; isk: number }[];
  rarity_mix: { rarity: string; volume: number }[];
  top_structures: { name: string; isk: number }[];
  invoice_status: { status: string; isk: number }[];
  recent_invoices: Invoice[];
};

export type Invoice = {
  id: number;
  invoice_number: string;
  character_name: string;
  corporation_name: string;
  structure_name: string;
  total_due_isk: string;
  amount_paid_isk: string;
  status: string;
  due_at: string;
  on_naughty_list: boolean;
};

export type MiningLog = {
  id: number;
  mined_date: string;
  structure_name: string;
  character_name: string;
  type_name: string;
  moon_rarity: string;
  quantity: number;
  isk_value: string;
};

export type Template = {
  id: number;
  slug: string;
  name: string;
  channel: string;
  subject: string;
  body: string;
  variables_json: string;
  active: boolean;
};

export type StructureTaxRule = {
  id: number;
  pattern: string;
  priority: number;
  r16_pct: string;
  r32_pct: string;
  r64_pct: string;
  active: boolean;
  notes: string;
};

export type OrgSettings = {
  org_name: string;
  corporation_id: number;
  observer_corporation_id: number;
  tax_corp_name: string;
  propaganda_tagline: string;
  mail_enabled: boolean;
  mail_sender_character: string;
};

export function fetchDashboard() {
  return emumsFetch<Dashboard>("/dashboard");
}

export function fetchInvoices(status?: string) {
  const q = status ? `?status=${status}` : "";
  return emumsFetch<Invoice[]>(`/moons/invoices${q}`);
}

export function fetchMiningLogs() {
  return emumsFetch<MiningLog[]>("/moons/mining-logs?limit=200");
}

export function fetchTemplates() {
  return emumsFetch<Template[]>("/templates");
}

export function fetchTaxRules() {
  return emumsFetch<StructureTaxRule[]>("/moons/tax-rules");
}

export function fetchSettings() {
  return emumsFetch<OrgSettings>("/settings");
}

// --- Coalition tools ---

export type ToolsHub = {
  categories: { slug: string; label: string; tools: { slug: string; label: string; public?: boolean }[] }[];
  authed_structures: AuthedStructure[];
  markets: string[];
};

export type AuthedStructure = {
  structure_id: number;
  structure_name: string;
  system_name: string;
  has_market: boolean;
  has_reprocessing: boolean;
};

export type SdeType = {
  type_id: number;
  name: string;
  group_name: string;
  category_name: string;
  volume_m3: number;
  base_price: number;
};

export type AuditProfile = {
  character_id: number;
  character_name: string;
  corporation_name: string;
  wallet_balance_isk: string;
  skill_points: number;
  assets_value_isk: string;
  snapshot_json: string;
};

export function fetchToolsHub() {
  return emumsFetch<ToolsHub>("/tools/hub");
}

export function fetchAuthedStructures() {
  return emumsFetch<AuthedStructure[]>("/tools/structures");
}

export function fetchAuditProfiles() {
  return emumsFetch<AuditProfile[]>("/tools/intelligence/audit");
}

export function fetchSdeSearch(q: string, limit = 200, category = "") {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (category) params.set("category", category);
  return emumsFetch<SdeType[]>(`/tools/intelligence/sde/search?${params}`);
}

export function fetchSdeCategories() {
  return emumsFetch<string[]>("/tools/intelligence/sde/categories");
}

export function fetchKillboard(scope = "alliance", refresh = true) {
  return emumsFetch<
    { character_id: number; character_name: string; kills: number; losses: number; isk_destroyed: string; isk_lost: string }[]
  >(`/tools/intelligence/killboard?scope=${scope}&refresh=${refresh ? "true" : "false"}`);
}

export type ShipFitting = {
  id: number;
  name: string;
  ship_type_id: number;
  ship_type_name: string;
  doctrine_slug: string;
  eft_text: string;
  tags_json: string;
  owner_character_id?: number | null;
  owner_character_name?: string;
};

export function fetchFittings() {
  return emumsFetch<ShipFitting[]>("/tools/operations/fittings");
}

export function fetchServiceLinks() {
  return emumsFetch<
    { id: number; service: string; label: string; url: string; description: string; requires_sso: boolean }[]
  >("/tools/administration/services");
}

export function fetchRattingPeriods() {
  return emumsFetch<
    { id: number; period_label: string; rate_pct: string; status: string; total_bounty_isk: string; total_collected_isk: string }[]
  >("/tools/administration/ratting");
}

export function fetchHrLeaves() {
  return emumsFetch<
    { id: number; character_name: string; start_date: string; end_date: string; reason: string; status: string }[]
  >("/tools/administration/hr/leaves");
}

export function fetchSrpLosses() {
  return emumsFetch<
    {
      id: number;
      killmail_id: number;
      character_name: string;
      ship_type_name: string;
      total_value_isk: string;
      srp_amount_isk: string;
      fit_grade: string;
      doctrine_match_pct: number;
      status: string;
      zkill_url: string;
    }[]
  >("/tools/administration/srp");
}

export function fetchMarketWatch() {
  return emumsFetch<
    { type_id: number; type_name: string; location_label: string; best_buy: string | null; best_sell: string | null; spread_pct: number | null }[]
  >("/tools/commerce/market-watch");
}

export function fetchCorpMarket() {
  return emumsFetch<
    { id: number; seller_character_name: string; type_id: number; type_name: string; quantity: number; unit_price_isk: string; listing_type: string; structure_name: string }[]
  >("/tools/commerce/corp-market");
}

export function fetchIndyHubJobs() {
  return emumsFetch<
    { id: number; job_type: string; requester: string; blueprint_name: string; status: string; runs: number; due_at: string | null }[]
  >("/tools/operations/indy-hub");
}

export function fetchIndustryCalcs() {
  return emumsFetch<
    { id: number; blueprint_name: string; runs: number; material_cost_isk: string; product_value_isk: string; profit_isk: string }[]
  >("/tools/operations/industry-calcs");
}

export type RouteBookmark = {
  id: number;
  name: string;
  origin_system: string;
  destination_system: string;
  origin_system_id: number | null;
  destination_system_id: number | null;
  jumps: number;
  security_max: number;
  route_mode: string;
  visibility: string;
  owner_character_name?: string;
  waypoint_system_ids: number[];
  route_json: string[];
  payload: Record<string, unknown>;
  share_token: string | null;
  share_url: string | null;
};

export function fetchRoutes(characterId?: number) {
  const qs = characterId ? `?character_id=${characterId}` : "";
  return emumsFetch<RouteBookmark[]>(`/tools/intelligence/routes${qs}`);
}

export function fetchPniStatements() {
  return emumsFetch<
    { id: number; period_label: string; status: string; total_income_isk: string; total_expense_isk: string }[]
  >("/tools/administration/pni");
}

export type SdeSystem = {
  system_id: number;
  name: string;
  security: number;
  region_name: string;
  constellation_name: string;
  x?: number;
  y?: number;
};

export type IndyBlueprint = {
  id: number;
  owner_character_name: string;
  owner_character_id?: number | null;
  owner_scope: string;
  type_id: number;
  type_name: string;
  material_efficiency: number;
  time_efficiency: number;
  runs: number;
  location_name: string;
  shared: boolean;
  copy_available: boolean;
};

export type IndyJobRecord = {
  id: number;
  character_name: string;
  owner_character_id?: number | null;
  installer_id?: number | null;
  installer_name?: string;
  job_id?: number | null;
  blueprint_name: string;
  activity: string;
  runs: number;
  status: string;
  location_name: string;
  started_at?: string | null;
  ends_at: string | null;
  output_type_name: string;
};

export type IndyCopyRequest = {
  id: number;
  requester: string;
  blueprint_name: string;
  runs: number;
  status: string;
  assignee: string;
  delivery_location: string;
  notes: string;
  created_at: string;
};

export type MaterialExchangeOrder = {
  id: number;
  character_name: string;
  type_id: number;
  type_name: string;
  side: string;
  quantity: number;
  unit_price_isk: string;
  status: string;
  created_at: string;
};

export function fetchSdeSystems(q = "") {
  return emumsFetch<SdeSystem[]>(`/tools/intelligence/sde/systems?q=${encodeURIComponent(q)}&limit=200`);
}

export function fetchMapGraph() {
  return emumsFetch<{ nodes: SdeSystem[]; edges: { from_system_id: number; to_system_id: number }[] }>(
    "/tools/intelligence/map/graph"
  );
}

export function fetchMapStatus() {
  return emumsFetch<{
    systems_total: number;
    systems_with_coords: number;
    systems_with_layout?: number;
    stargate_links: number;
    full_sde_loaded: boolean;
    jump_drive_ready: boolean;
    layout_ready?: boolean;
  }>("/tools/intelligence/map/status");
}

export function fetchMapAtlas() {
  return emumsFetch<{
    version: number;
    systems: unknown[];
    edges: unknown[];
    system_count: number;
    edge_count: number;
  }>("/tools/intelligence/map/atlas");
}

export function fetchJumpShips() {
  return emumsFetch<
    {
      slug: string;
      name: string;
      category: string;
      base_range_ly: number;
      fuel_per_ly: number;
      fuel_type: string;
      fuel_type_id: number;
      is_jump_freighter: boolean;
    }[]
  >("/tools/intelligence/map/jump-ships");
}

export function fetchIndyBlueprints() {
  return emumsFetch<IndyBlueprint[]>("/tools/operations/blueprints");
}

export function fetchIndyIndustryJobs() {
  return emumsFetch<IndyJobRecord[]>("/tools/operations/industry-jobs");
}

export function fetchIndyCopyRequests() {
  return emumsFetch<IndyCopyRequest[]>("/tools/operations/copy-requests");
}

export function fetchMaterialExchange() {
  return emumsFetch<MaterialExchangeOrder[]>("/tools/operations/material-exchange");
}

export type IndustrialProject = {
  id: number;
  project_code: string;
  name: string;
  container_name: string;
  owner_character_name: string;
  status: string;
  material_cost_isk: string;
  job_cost_isk: string;
  true_cost_isk: string;
  notes: string;
  stock_lines: { type_name: string; quantity: number; unit_cost_isk: string; container_name: string }[];
  job_lines: { description: string; activity: string; runs: number; cost_isk: string; structure_name: string }[];
};

export type BlueprintContract = {
  id: number;
  contract_id: number;
  blueprint_name: string;
  seller_name: string;
  location: string;
  price_isk: string;
  runs: number;
  material_efficiency: number;
  time_efficiency: number;
};

export type StorefrontCatalogItem = {
  key: string;
  kind: "item" | "kit";
  type_id: number | null;
  kit_id: number | null;
  name: string;
  quantity: number;
  synced_qty: number;
  fake_qty_add: number;
  unit_price_isk: number | null;
  janice_split_isk: number | null;
  price_source: string;
  price_label: string | null;
  hidden: boolean;
  note: string;
  kit_items: { type_id: number; type_name: string; quantity: number }[];
  group_name?: string;
  category_name?: string;
  low_stock?: boolean;
  line_total_isk?: number | null;
};

export type StorefrontPickupLocation = {
  id: number;
  label: string;
  structure_name: string;
  structure_id: number;
  system_name: string;
  location_hint: string;
  is_default: boolean;
  active: boolean;
  sort_order: number;
};

export type StorefrontCatalog = {
  enabled: boolean;
  corp_name: string;
  price_hub: string;
  price_hub_label: string;
  pricing_source: string;
  janice_configured: boolean;
  items: StorefrontCatalogItem[];
  pickup_locations: StorefrontPickupLocation[];
  inventory_source: {
    corp_id: number;
    corp_hangar_flag: string;
    corp_hangar_division?: number;
    scope?: string;
    sync_character_count?: number;
    sync_hangar_type_count?: number;
    sync_hangar_qty_total?: number;
    corp_assets_scope_count?: number;
    structure_name_contains?: string;
    system_name_contains?: string;
    structure_id?: number;
    inventory_character_ids?: number[];
  };
  summary?: {
    item_count: number;
    priced_count: number;
    unpriced_count: number;
    total_stock_units: number;
    kit_count: number;
    categories: string[];
    low_stock_count: number;
  };
};

export type IndustrialStructure = {
  structure_id: number;
  structure_name: string;
  system_name: string;
  location_label: string;
  material_bonus_pct: number;
  time_bonus_pct: number;
  tax_pct: number;
};

export function fetchIndustrialProjects() {
  return emumsFetch<IndustrialProject[]>("/tools/operations/industrial-planning/projects");
}

export function fetchIndustrialStructures(locationFilter = "all") {
  return emumsFetch<IndustrialStructure[]>(
    `/tools/operations/industrial-planning/structures?location_filter=${locationFilter}`
  );
}

export function fetchBlueprintContracts() {
  return emumsFetch<BlueprintContract[]>("/tools/operations/blueprint-contracts");
}

export function fetchStorefront() {
  return emumsFetch<StorefrontCatalog>("/tools/operations/storefront");
}

export const EMPTY_STOREFRONT_CATALOG: StorefrontCatalog = {
  enabled: true,
  corp_name: "Solar Extraction Venture",
  price_hub: "jita",
  price_hub_label: "Jita 4-4",
  pricing_source: "janice split",
  janice_configured: false,
  items: [],
  pickup_locations: [],
  summary: {
    item_count: 0,
    priced_count: 0,
    unpriced_count: 0,
    total_stock_units: 0,
    kit_count: 0,
    categories: [],
    low_stock_count: 0,
  },
  inventory_source: {
    corp_id: 98829530,
    corp_hangar_flag: "CorpSAG1",
    structure_name_contains: "",
    system_name_contains: "",
    structure_id: 0,
    inventory_character_ids: [],
    scope: "all_corp_structures",
    sync_character_count: 0,
  },
};
