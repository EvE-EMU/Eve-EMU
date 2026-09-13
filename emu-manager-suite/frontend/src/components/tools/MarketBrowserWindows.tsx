"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMarketBrowser } from "@/components/tools/MarketBrowserContext";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EveWindow } from "@/components/ui";
import { KpiStrip, KpiTile, SectionHead, StatusStrip } from "@/components/ui";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";

type MarketLocation =
  | {
      id: string;
      kind: "region" | "station" | "all_stations";
      slug: string;
      region_id: number | null;
      name: string;
      station_id: number | null;
    }
  | {
      id: string;
      kind: "structure";
      structure_id: number;
      name: string;
      system_name: string;
      owner_character_id?: number;
      owner_character_name?: string | null;
      esi_linked?: boolean;
    };

type SdeTypeRow = { type_id: number; name: string; group_name: string; category_name?: string };

type MarketOrder = {
  order_id: number | null;
  price: number;
  volume_remain: number;
  volume_total: number;
  min_volume: number;
  range: string;
  issued?: string;
  location_label: string;
  is_buy_order: boolean;
  source?: string;
};

type OrdersResult = {
  location_kind: string;
  location_label: string;
  region_id?: number;
  type_id: number;
  type_name: string;
  buy_orders: MarketOrder[];
  sell_orders: MarketOrder[];
  summary: {
    buy_count: number;
    sell_count: number;
    best_buy: number | null;
    best_sell: number | null;
    spread: number | null;
  };
  data_source?: string;
  data_note?: string;
  error?: string;
  message?: string;
};

type HistoryDay = {
  day: string;
  average: number;
  highest: number;
  lowest: number;
  volume: number;
};

function fmtIsk(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function OrdersTable({ orders, side }: { orders: MarketOrder[]; side: "buy" | "sell" }) {
  if (!orders.length) {
    return <p className="text-[10px] text-[var(--text-muted)]">No {side} orders.</p>;
  }
  return (
    <table className="eve-table text-[10px]">
      <thead>
        <tr>
          <th>Price</th>
          <th>Vol</th>
          <th>Location</th>
          <th>Range</th>
          <th>Issued</th>
        </tr>
      </thead>
      <tbody>
        {orders.slice(0, 40).map((o) => (
          <tr key={o.order_id}>
            <td className="num">{fmtIsk(o.price)}</td>
            <td className="num">{o.volume_remain.toLocaleString()}</td>
            <td className="truncate max-w-[140px]" title={o.location_label}>
              {o.location_label}
            </td>
            <td>{o.range}</td>
            <td>{o.issued ? o.issued.slice(0, 10) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MarketBrowserWindows() {
  return (
    <Suspense fallback={null}>
      <MarketBrowserWindowsInner />
    </Suspense>
  );
}

function MarketBrowserWindowsInner() {
  const searchParams = useSearchParams();
  const marketBrowser = useMarketBrowser();
  const pendingFocus = marketBrowser?.focus ?? null;
  const autoLoadNonce = useRef(0);
  const [npcLocations, setNpcLocations] = useState<MarketLocation[]>([]);
  const [sharedLocations, setSharedLocations] = useState<MarketLocation[]>([]);
  const [selectedId, setSelectedId] = useState<string>("all:stations");
  const [typeQ, setTypeQ] = useState("Tritanium");
  const [typeRows, setTypeRows] = useState<SdeTypeRow[]>([]);
  const [selectedType, setSelectedType] = useState<SdeTypeRow | null>(null);
  const [orders, setOrders] = useState<OrdersResult | null>(null);
  const [history, setHistory] = useState<HistoryDay[]>([]);
  const [historyRegion, setHistoryRegion] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [orderTab, setOrderTab] = useState<"sell" | "buy">("sell");

  const selected = useMemo(() => {
    return [...npcLocations, ...sharedLocations].find((l) => l.id === selectedId) ?? null;
  }, [npcLocations, sharedLocations, selectedId]);

  useEffect(() => {
    fetch("/api/tools/market-browser/locations", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        setNpcLocations(data.npc_hubs ?? []);
        setSharedLocations(data.shared_structures ?? []);
      })
      .catch(() => setError("Failed to load market locations"));
  }, []);

  const searchTypes = useCallback(async () => {
    const res = await fetch(`/api/tools/sde?q=${encodeURIComponent(typeQ)}`, { cache: "no-store" });
    if (!res.ok) return;
    const rows = await res.json();
    setTypeRows(rows);
    if (rows.length === 1) setSelectedType(rows[0]);
  }, [typeQ]);

  useEffect(() => {
    void searchTypes();
  }, []);

  useEffect(() => {
    const typeId = searchParams.get("type_id");
    const typeName = searchParams.get("type_name");
    if (!typeId) return;
    const id = Number(typeId);
    if (!Number.isFinite(id)) return;
    setSelectedType({
      type_id: id,
      name: typeName || `Type ${id}`,
      group_name: "",
    });
    if (typeName) setTypeQ(typeName);
  }, [searchParams]);

  useEffect(() => {
    if (!pendingFocus) return;
    setSelectedType({
      type_id: pendingFocus.typeId,
      name: pendingFocus.typeName,
      group_name: "",
    });
    setTypeQ(pendingFocus.typeName);
    if (pendingFocus.autoLoad) {
      autoLoadNonce.current = pendingFocus.nonce;
    }
  }, [pendingFocus]);

  const loadMarket = useCallback(async () => {
    if (!selected || !selectedType) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        kind: selected.kind,
        location_id: String(
          selected.kind === "structure"
            ? selected.structure_id
            : selected.kind === "station"
              ? selected.station_id ?? 0
              : selected.kind === "all_stations"
                ? 0
                : selected.region_id ?? 0
        ),
        type_id: String(selectedType.type_id),
      });
      if (selected.kind === "station") {
        params.set("region_id", String(selected.region_id));
      }
      const res = await fetch(`/api/tools/market-browser/orders?${params}`, { cache: "no-store" });
      const data: OrdersResult = await res.json();
      if (data.error) {
        setOrders(null);
        setError(data.message ?? data.error);
      } else {
        setOrders(data);
        setError("");
      }

      const regionId =
        selected.kind === "structure"
          ? null
          : selected.kind === "all_stations"
            ? 10000002
            : selected.kind === "station"
              ? selected.region_id
              : selected.region_id;
      if (regionId) {
        setHistoryRegion(regionId);
        const hres = await fetch(
          `/api/tools/market-browser/history?region_id=${regionId}&type_id=${selectedType.type_id}&max_days=360`,
          { cache: "no-store" }
        );
        const hdata = await hres.json();
        setHistory(hdata.days ?? []);
      } else {
        setHistory([]);
        setHistoryRegion(null);
      }
    } catch {
      setError("Market request failed");
    } finally {
      setLoading(false);
    }
  }, [selected, selectedType]);

  useEffect(() => {
    const urlTypeId = searchParams.get("type_id");
    const shouldAutoLoad =
      (urlTypeId && selectedType && selected) ||
      (pendingFocus?.autoLoad && pendingFocus.nonce === autoLoadNonce.current && selectedType && selected);
    if (!shouldAutoLoad) return;
    void loadMarket();
  }, [searchParams, pendingFocus, selectedType, selected, loadMarket]);

  return (
    <>
      <EveWindow
        id="market-browser"
        title="Market Browser"
        defaultX={24}
        defaultY={24}
        defaultWidth={680}
        defaultHeight={620}
      >
        <StatusStrip>
          Live ESI order books — NPC trade hubs and structure markets shared via coalition ESI
        </StatusStrip>

        <div className="eve-market-browser-layout">
          <aside className="eve-market-browser-locations">
            <SectionHead>NPC stations</SectionHead>
            <ul className="eve-market-location-list">
              {npcLocations.map((loc) => (
                <li key={loc.id}>
                  <button
                    type="button"
                    className={`eve-market-location-btn ${selectedId === loc.id ? "is-active" : ""}`}
                    onClick={() => setSelectedId(loc.id)}
                  >
                    {loc.name}
                  </button>
                </li>
              ))}
            </ul>
            <SectionHead>Shared ESI structures</SectionHead>
            {sharedLocations.length === 0 ? (
              <p className="text-[9px] text-[var(--text-muted)]">No authed structure markets configured.</p>
            ) : (
              <ul className="eve-market-location-list">
                {sharedLocations.map((loc) => (
                  <li key={loc.id}>
                    <button
                      type="button"
                      className={`eve-market-location-btn ${selectedId === loc.id ? "is-active" : ""}`}
                      onClick={() => setSelectedId(loc.id)}
                    >
                      {loc.name}
                      {loc.kind === "structure" ? (
                        <span className="block text-[8px] text-[var(--text-muted)]">{loc.system_name}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </aside>

          <div className="eve-market-browser-main">
            <div className="flex flex-wrap gap-2 items-end mb-2">
              <label className="flex flex-col gap-0.5 flex-1 min-w-[160px]">
                <span className="text-[var(--text-muted)]">Item</span>
                <input
                  className="eve-input"
                  value={typeQ}
                  onChange={(e) => setTypeQ(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchTypes()}
                />
              </label>
              <button type="button" className="eve-btn" onClick={searchTypes}>
                Search SDE
              </button>
              <select
                className="eve-select min-w-[180px]"
                value={selectedType?.type_id ?? ""}
                onChange={(e) => {
                  const row = typeRows.find((r) => r.type_id === Number(e.target.value));
                  setSelectedType(row ?? null);
                }}
              >
                <option value="">Select type…</option>
                {typeRows.map((r) => (
                  <option key={r.type_id} value={r.type_id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="eve-btn eve-btn-primary"
                disabled={loading || !selectedType || !selected}
                onClick={loadMarket}
              >
                {loading ? "Loading…" : "Load orders"}
              </button>
            </div>

            {selectedType ? (
              <div className="flex items-center gap-2 mb-2">
                <EveTypeIcon
                  typeId={selectedType.type_id}
                  size={28}
                  categoryName={selectedType.category_name}
                  groupName={selectedType.group_name}
                />
                <strong>{selectedType.name}</strong>
                <span className="text-[var(--text-muted)]">@ {selected?.name}</span>
              </div>
            ) : null}

            {error ? <p className="text-[var(--danger)] text-[10px] mb-2">{error}</p> : null}

            {orders && !orders.error ? (
              <>
                <KpiStrip>
                  <KpiTile label="Best sell" value={fmtIsk(orders.summary.best_sell)} tone="ok" />
                  <KpiTile label="Best buy" value={fmtIsk(orders.summary.best_buy)} />
                  <KpiTile
                    label="Spread"
                    value={orders.summary.spread != null ? fmtIsk(orders.summary.spread) : "—"}
                    tone="accent"
                  />
                  <KpiTile label="Sell orders" value={String(orders.summary.sell_count)} />
                  <KpiTile label="Buy orders" value={String(orders.summary.buy_count)} />
                </KpiStrip>

                {orders.data_note ? (
                  <p className="text-[var(--text-muted)] text-[9px] mb-2 leading-snug">{orders.data_note}</p>
                ) : null}

                <div className="flex gap-1 my-2">
                  <button
                    type="button"
                    className={`eve-btn ${orderTab === "sell" ? "eve-btn-primary" : ""}`}
                    onClick={() => setOrderTab("sell")}
                  >
                    Sell orders ({orders.sell_orders.length})
                  </button>
                  <button
                    type="button"
                    className={`eve-btn ${orderTab === "buy" ? "eve-btn-primary" : ""}`}
                    onClick={() => setOrderTab("buy")}
                  >
                    Buy orders ({orders.buy_orders.length})
                  </button>
                </div>

                <div className="overflow-auto max-h-[180px] mb-2">
                  <OrdersTable orders={orderTab === "sell" ? orders.sell_orders : orders.buy_orders} side={orderTab} />
                </div>
              </>
            ) : null}

            {history.length > 0 && historyRegion ? (
              <div className="eve-market-history-chart">
                <SectionHead>Regional history (360d)</SectionHead>
                <div className="h-36 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={history.slice(-360)} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                      <CartesianGrid stroke="#2a3540" strokeDasharray="2 2" vertical={false} />
                      <XAxis
                        dataKey="day"
                        tick={{ fill: "#9aa8b4", fontSize: 8 }}
                        tickFormatter={(v) => String(v).slice(5)}
                        axisLine={{ stroke: "#2a3540" }}
                        tickLine={false}
                      />
                      <YAxis tick={{ fill: "#9aa8b4", fontSize: 8 }} axisLine={false} tickLine={false} width={48} />
                      <Tooltip
                        contentStyle={{ background: "#12181f", border: "1px solid #2a3540", fontSize: 10 }}
                        formatter={(v: number) => fmtIsk(v)}
                      />
                      <Area type="monotone" dataKey="average" stroke="#9ed0e0" fill="#3a6878" fillOpacity={0.35} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : selected?.kind === "structure" && orders ? (
              <p className="text-[9px] text-[var(--text-muted)]">
                ESI does not publish structure-specific price history — use live orders above.
              </p>
            ) : null}
          </div>
        </div>
      </EveWindow>

      <EveWindow
        id="market-stations"
        title="Market Locations"
        defaultX={720}
        defaultY={24}
        defaultWidth={320}
        defaultHeight={420}
      >
        <StatusStrip>NPC trade hub stations and coalition structure markets</StatusStrip>
        <SectionHead>NPC regions</SectionHead>
        <ul className="text-[10px] space-y-1 mb-3">
          {npcLocations
            .filter((l) => l.kind === "region")
            .map((l) => (
              <li key={l.id}>
                <button type="button" className="text-[var(--link)]" onClick={() => setSelectedId(l.id)}>
                  {l.name}
                </button>
              </li>
            ))}
        </ul>
        <SectionHead>Shared structure markets</SectionHead>
        <ul className="text-[10px] space-y-2">
          {sharedLocations.map((loc) => (
            <li key={loc.id} className="border border-[var(--edge-dim)] p-2">
              <button type="button" className="text-left w-full" onClick={() => setSelectedId(loc.id)}>
                <strong>{loc.name}</strong>
                {loc.kind === "structure" ? (
                  <>
                    <div className="text-[9px] text-[var(--text-muted)]">{loc.system_name}</div>
                    <div className="text-[9px]">
                      {loc.esi_linked ? "ESI linked" : "Awaiting ESI token"}
                      {loc.owner_character_name ? ` · ${loc.owner_character_name}` : ""}
                    </div>
                  </>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </EveWindow>
    </>
  );
}
