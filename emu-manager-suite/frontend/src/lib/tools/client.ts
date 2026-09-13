/** Client-side tools API (via Next.js BFF). */

export type BuybackLocation = {
  id: string;
  label: string;
  fee_pct: number;
  market: string;
};

export type AppraisalResult = {
  id?: number;
  share_token?: string;
  share_url?: string;
  sell_market: string;
  buy_market: string;
  sell_market_label: string;
  buy_market_label: string;
  janice_configured: boolean;
  janice_code?: string | null;
  janice_url?: string | null;
  totals: { total_sell: number; total_buy: number; split_value: number; total_refine?: number; delta_isk?: number; recommendation?: string };
  unresolved: string[];
  lines: {
    type_id?: number;
    name: string;
    quantity: number;
    single_sell?: number;
    single_buy?: number;
    single_split?: number;
    single_refine?: number;
    total_sell?: number;
    total_buy?: number;
    total_split?: number;
    sell_total?: number;
    refine_total?: number;
    delta_isk?: number;
    recommendation?: string;
    best_total?: number;
    basis_unit?: number;
    basis_total?: number;
    pricing_mode?: string;
  }[];
  fee_pct?: number;
  contract_value_isk?: number;
  fee_basis_isk?: number;
  item_location?: string;
  item_location_label?: string;
  contract_code?: string;
  contract_description?: string;
  buyback_locations?: BuybackLocation[];
};

export type MarketTrackerRow = {
  type_id: number;
  type_name: string;
  hub_buy: number | null;
  hub_sell: number | null;
  local_buy: number | null;
  local_sell: number | null;
  spread_pct: number | null;
  location_label: string;
};

export type MarketTrackerResult = {
  hub: string;
  hub_label: string;
  system_label: string;
  system_id: number | null;
  region_id: number | null;
  janice_configured: boolean;
  rows: MarketTrackerRow[];
};

export async function postAppraisal(body: {
  text: string;
  sell_market?: string;
  buy_market?: string;
}): Promise<AppraisalResult> {
  const res = await fetch("/api/tools/appraisal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAppraisal(token: string): Promise<AppraisalResult> {
  const res = await fetch(`/api/tools/appraisal/${encodeURIComponent(token)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function postBuyback(body: {
  text: string;
  fee_pct?: number;
  sell_market?: string;
  item_location?: string;
}): Promise<AppraisalResult> {
  const res = await fetch("/api/tools/buyback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getBuyback(token: string): Promise<AppraisalResult> {
  const res = await fetch(`/api/tools/buyback/${encodeURIComponent(token)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function postRefineCompare(body: {
  text: string;
  sell_market?: string;
}): Promise<AppraisalResult> {
  const res = await fetch("/api/tools/refine-compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchBuybackLocations(): Promise<BuybackLocation[]> {
  const res = await fetch("/api/tools/buyback/locations", { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchMarketTracker(params: {
  hub?: string;
  system_q?: string;
  item_q?: string;
  limit?: number;
}): Promise<MarketTrackerResult> {
  const q = new URLSearchParams();
  if (params.hub) q.set("hub", params.hub);
  if (params.system_q) q.set("system_q", params.system_q);
  if (params.item_q) q.set("item_q", params.item_q);
  if (params.limit) q.set("limit", String(params.limit));
  const res = await fetch(`/api/tools/market-tracker?${q}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitCorpMarketOrder(body: {
  buyer_character_name: string;
  buyer_character_id?: number;
  type_id?: number;
  type_name?: string;
  quantity: number;
  unit_price_isk: number;
  delivery_location: string;
  notes?: string;
}) {
  const res = await fetch("/api/tools/corp-market/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function searchSde(q: string) {
  const res = await fetch(`/api/tools/sde?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error("SDE search failed");
  return res.json();
}

export async function submitLeave(body: {
  character_name: string;
  character_id?: number;
  start_date: string;
  end_date: string;
  reason?: string;
}) {
  const res = await fetch("/api/tools/hr/leaves", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
