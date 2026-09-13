"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { EveWindow } from "@/components/ui";
import { DesktopSurface, useWindowManager, useWindowManagerOptional, WindowDesktop } from "@/components/WindowManager";
import { DataField, KpiStrip, KpiTile, SectionHead, StatusStrip } from "@/components/ui";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { typeIconUrl, typeRenderUrl, characterPortraitUrl } from "@/lib/evetech";
import { CharacterSheetPanel } from "@/components/tools/CharacterSheetPanel";
import { InteractionAuditPanel } from "@/components/tools/InteractionAuditPanel";
import { WebhookNotificationPanel } from "@/components/tools/WebhookNotificationPanel";
import { PiOverviewPanel } from "@/components/tools/PiOverviewPanel";
import { KillboardPanel } from "@/components/tools/KillboardPanel";
import { SrpProgramPanel } from "@/components/tools/SrpProgramPanel";
import { CharSheetInspectProvider } from "@/components/tools/CharSheetInspectContext";
import { AssetShipFittingPanel } from "@/components/tools/AssetShipFittingPanel";
import { SdeItemDetailPanel } from "@/components/tools/SdeItemDetailPanel";
import { SystemDetailPanel } from "@/components/tools/SystemDetailPanel";
import { WikiArticlePanel } from "@/components/tools/WikiPanels";
import { StructureFuelPanel } from "@/components/tools/StructureFuelPanel";
import type { AssetTreeNode } from "@/components/tools/CharacterSheetAssets";
import { TOOLS, toolsForCategory, toolHref } from "@/lib/tools/registry";
import { openToolInDesktop } from "@/lib/openTool";
import {
  fetchBuybackLocations,
  fetchMarketTracker,
  getAppraisal,
  getBuyback,
  postAppraisal,
  postBuyback,
  postRefineCompare,
  submitCorpMarketOrder,
  type AppraisalResult,
  type BuybackLocation,
  type MarketTrackerResult,
} from "@/lib/tools/client";
import { CharSheetSortButton } from "@/components/tools/CharSheetTableToolbar";
import { sortByKey, useTableSort } from "@/lib/useTableSort";
import type { ToolsHub } from "@/lib/api";

function fmtIsk(v: string | number | null | undefined) {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function CommerceShareFocus() {
  const searchParams = useSearchParams();
  const wm = useWindowManagerOptional();

  useEffect(() => {
    if (!wm) return;
    const buyback = searchParams.get("buyback");
    const appraisal = searchParams.get("appraisal");
    if (buyback) {
      wm.openWindow("buyback");
      wm.focusWindow("buyback");
    } else if (appraisal) {
      wm.openWindow("appraisal");
      wm.focusWindow("appraisal");
    }
  }, [searchParams, wm]);

  return null;
}

function PasteToolPanel({
  mode,
  markets,
  structures,
}: {
  mode: "appraisal" | "buyback" | "refine";
  markets: string[];
  structures: { structure_name: string; has_market: boolean }[];
}) {
  type LineSort = "name" | "qty" | "sell" | "refine" | "delta" | "best";
  const { sortKey, sortAsc, toggleSort } = useTableSort<LineSort>("delta", false);
  const searchParams = useSearchParams();
  const [text, setText] = useState("");
  const [market, setMarket] = useState("jita");
  const [itemLocation, setItemLocation] = useState("");
  const [locations, setLocations] = useState<BuybackLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AppraisalResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode !== "buyback") return;
    void fetchBuybackLocations().then((rows) => {
      setLocations(rows);
      if (rows.length) setItemLocation(rows[0].id);
    });
  }, [mode]);

  useEffect(() => {
    const token = searchParams.get(mode === "buyback" ? "buyback" : "appraisal");
    if (!token) return;
    setLoading(true);
    const load = mode === "buyback" ? getBuyback(token) : getAppraisal(token);
    load
      .then((data) => {
        setResult(data);
        if (data.item_location) setItemLocation(data.item_location);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load share link"))
      .finally(() => setLoading(false));
  }, [searchParams, mode]);

  const selectedLocation = locations.find((l) => l.id === itemLocation);

  const run = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data =
        mode === "buyback"
          ? await postBuyback({
              text,
              sell_market: selectedLocation?.market || market,
              item_location: itemLocation,
            })
          : mode === "refine"
            ? await postRefineCompare({ text, sell_market: market })
            : await postAppraisal({ text, sell_market: market, buy_market: market });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, [text, market, itemLocation, mode, selectedLocation?.market]);

  const structMarkets = structures.filter((s) => s.has_market);

  const sortedLines = useMemo(() => {
    if (!result?.lines?.length) return [];
    return sortByKey(result.lines, sortKey, sortAsc, (line, key) => {
      if (key === "name") return line.name;
      if (key === "qty") return line.quantity;
      if (key === "sell") return line.sell_total ?? line.total_sell ?? 0;
      if (key === "refine") return line.refine_total ?? line.total_buy ?? 0;
      if (key === "delta") return line.delta_isk ?? 0;
      return line.best_total ?? 0;
    });
  }, [result?.lines, sortKey, sortAsc]);

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      <StatusStrip>
        {mode === "buyback"
          ? "Paste inventory and select where items are located. Fee is set from location; quote uses Janice JBV/reprocess unless raw market is higher."
          : mode === "refine"
            ? "Compare selling unrefined at the hub vs reprocessing (Janice JBV/buy). Green recommendation = better option for that line."
            : "Janice appraisal — paste inventory for buy / split / sell totals and share link."}
      </StatusStrip>
      <div className="flex flex-wrap gap-2 items-center">
        {mode === "buyback" ? (
          <label className="text-[10px] text-[var(--text-muted)]">
            Item location
            <select
              className="eve-select ml-1 min-w-[200px]"
              value={itemLocation}
              onChange={(e) => setItemLocation(e.target.value)}
            >
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.label} ({loc.fee_pct}%)
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="text-[10px] text-[var(--text-muted)]">
            Hub
            <select className="eve-select ml-1" value={market} onChange={(e) => setMarket(e.target.value)}>
              {markets.map((m) => (
                <option key={m} value={m}>
                  {m.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="button" className="eve-btn eve-btn-primary" disabled={loading || !text.trim()} onClick={run}>
          {loading
            ? "Pricing…"
            : mode === "buyback"
              ? "Quote buyback"
              : mode === "refine"
                ? "Compare refine vs sell"
                : "Appraise"}
        </button>
      </div>
      {mode === "buyback" && selectedLocation ? (
        <p className="text-[9px] text-[var(--text-muted)]">
          Buyback fee: {selectedLocation.fee_pct}% of Janice basis @ {selectedLocation.market.toUpperCase()}
        </p>
      ) : null}
      {structMarkets.length > 0 ? (
        <p className="text-[9px] text-[var(--text-muted)]">
          Authed structure markets: {structMarkets.map((s) => s.structure_name).join(", ")}
        </p>
      ) : null}
      <textarea
        className="eve-textarea flex-1 min-h-[120px] font-mono text-[10px]"
        placeholder="Paste from EVE client here (tab-separated lines)…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {error ? <p className="text-[var(--danger)] text-[10px]">{error}</p> : null}
      {result ? (
        <div className="flex flex-col gap-1 min-h-0 overflow-auto">
          <KpiStrip>
            {mode === "buyback" ? (
              <KpiTile label="Contract value" value={`${fmtIsk(result.contract_value_isk)} ISK`} tone="ok" />
            ) : mode === "refine" ? (
              <>
                <KpiTile
                  label="Best action"
                  value={(result.totals.recommendation ?? "—").toUpperCase()}
                  tone={result.totals.recommendation === "sell" ? "warn" : "ok"}
                />
                <KpiTile label="Sell @ hub" value={`${fmtIsk(result.totals.total_sell)} ISK`} />
                <KpiTile label="Refine value" value={`${fmtIsk(result.totals.total_refine)} ISK`} tone="ok" />
                <KpiTile label="Spread" value={`${fmtIsk(result.totals.delta_isk)} ISK`} />
              </>
            ) : (
              <KpiTile label="Split value" value={`${fmtIsk(result.totals.split_value)} ISK`} />
            )}
            {mode !== "refine" ? (
              <>
                <KpiTile label="Sell total" value={`${fmtIsk(result.totals.total_sell)} ISK`} />
                <KpiTile label="Buy total" value={`${fmtIsk(result.totals.total_buy)} ISK`} />
              </>
            ) : null}
          </KpiStrip>
          {result.share_url ? (
            <DataField label="Share link">
              <a href={result.share_url} className="text-[var(--link)] text-[10px] break-all">
                {result.share_url}
              </a>
            </DataField>
          ) : null}
          {mode === "buyback" && result.contract_description ? (
            <DataField label="Contract description (paste in-game)">
              <code className="text-[10px] text-[var(--accent)]">{result.contract_description}</code>
            </DataField>
          ) : null}
          {result.janice_url ? (
            <DataField label="Janice appraisal">
              <a href={result.janice_url} className="text-[var(--link)] text-[10px]" target="_blank" rel="noreferrer">
                {result.janice_code || result.janice_url}
              </a>
            </DataField>
          ) : null}
          {result.unresolved?.length ? (
            <p className="text-[var(--warn)] text-[9px]">Unresolved: {result.unresolved.join(", ")}</p>
          ) : null}
          <table className="eve-table text-[10px]">
            <thead>
              <tr>
                <th />
                <th>
                  <CharSheetSortButton label="Item" active={sortKey === "name"} asc={sortAsc} onClick={() => toggleSort("name")} />
                </th>
                <th>
                  <CharSheetSortButton label="Qty" active={sortKey === "qty"} asc={sortAsc} onClick={() => toggleSort("qty")} align="right" />
                </th>
                {mode === "buyback" ? (
                  <>
                    <th>Basis</th>
                    <th>Mode</th>
                  </>
                ) : mode === "refine" ? (
                  <>
                    <th>
                      <CharSheetSortButton label="Sell @ hub" active={sortKey === "sell"} asc={sortAsc} onClick={() => toggleSort("sell")} align="right" />
                    </th>
                    <th>
                      <CharSheetSortButton label="Refine" active={sortKey === "refine"} asc={sortAsc} onClick={() => toggleSort("refine")} align="right" />
                    </th>
                    <th>
                      <CharSheetSortButton label="Δ ISK" active={sortKey === "delta"} asc={sortAsc} onClick={() => toggleSort("delta")} align="right" />
                    </th>
                    <th>Pick</th>
                  </>
                ) : (
                  <>
                    <th>
                      <CharSheetSortButton label="Sell" active={sortKey === "sell"} asc={sortAsc} onClick={() => toggleSort("sell")} align="right" />
                    </th>
                    <th>
                      <CharSheetSortButton label="Buy" active={sortKey === "refine"} asc={sortAsc} onClick={() => toggleSort("refine")} align="right" />
                    </th>
                    <th>Split</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedLines.map((line, i) => (
                <tr key={`${line.name}-${i}`}>
                  <td>
                    {line.type_id ? (
                      <img src={typeIconUrl(line.type_id, 32)} alt="" width={24} height={24} className="rounded-sm" />
                    ) : null}
                  </td>
                  <td>{line.name}</td>
                  <td className="num">{line.quantity.toLocaleString()}</td>
                  {mode === "buyback" ? (
                    <>
                      <td className="num">{line.basis_total != null ? fmtIsk(line.basis_total) : "—"}</td>
                      <td>{line.pricing_mode ?? "—"}</td>
                    </>
                  ) : mode === "refine" ? (
                    <>
                      <td className="num">{line.sell_total != null ? fmtIsk(line.sell_total) : "—"}</td>
                      <td className="num">{line.refine_total != null ? fmtIsk(line.refine_total) : "—"}</td>
                      <td className="num">{line.delta_isk != null ? fmtIsk(line.delta_isk) : "—"}</td>
                      <td className={line.recommendation === "sell" ? "text-[var(--warn)]" : "text-[var(--ok)]"}>
                        {line.recommendation === "sell" ? "Sell" : line.recommendation === "refine" ? "Refine" : "Tie"}
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="num">{line.total_sell != null ? fmtIsk(line.total_sell) : "—"}</td>
                      <td className="num">{line.total_buy != null ? fmtIsk(line.total_buy) : "—"}</td>
                      <td className="num">{line.total_split != null ? fmtIsk(line.total_split) : "—"}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function MarketTrackerPanel({ markets }: { markets: string[] }) {
  const [hub, setHub] = useState("jita");
  const [systemQ, setSystemQ] = useState("");
  const [itemQ, setItemQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MarketTrackerResult | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await fetchMarketTracker({
        hub,
        system_q: systemQ.trim() || undefined,
        item_q: itemQ.trim() || undefined,
        limit: 25,
      });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tracker failed");
    } finally {
      setLoading(false);
    }
  }, [hub, systemQ, itemQ]);

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      <StatusStrip>
        Hub vs selected system — Janice hub medians vs ESI local orders. Top 25 when no item search.
      </StatusStrip>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[10px] text-[var(--text-muted)]">
          Hub
          <select className="eve-select ml-1" value={hub} onChange={(e) => setHub(e.target.value)}>
            {markets.map((m) => (
              <option key={m} value={m}>
                {m.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[10px] text-[var(--text-muted)]">
          System
          <input
            className="eve-input ml-1 w-32"
            placeholder="Jita, Amarr…"
            value={systemQ}
            onChange={(e) => setSystemQ(e.target.value)}
          />
        </label>
        <label className="text-[10px] text-[var(--text-muted)]">
          Item
          <input
            className="eve-input ml-1 w-32"
            placeholder="Search item…"
            value={itemQ}
            onChange={(e) => setItemQ(e.target.value)}
          />
        </label>
        <button type="button" className="eve-btn eve-btn-primary" disabled={loading} onClick={load}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {error ? <p className="text-[var(--danger)] text-[10px]">{error}</p> : null}
      {data ? (
        <p className="text-[9px] text-[var(--text-muted)]">
          {data.hub_label} vs {data.system_label}
          {!data.janice_configured ? " · Janice API not configured" : ""}
        </p>
      ) : null}
      <div className="overflow-auto flex-1">
        <table className="eve-table text-[10px]">
          <thead>
            <tr>
              <th />
              <th>Item</th>
              <th>Hub buy</th>
              <th>Hub sell</th>
              <th>Local buy</th>
              <th>Local sell</th>
              <th>Spread</th>
            </tr>
          </thead>
          <tbody>
            {(data?.rows ?? []).map((row) => (
              <tr key={row.type_id}>
                <td>
                  <img src={typeIconUrl(row.type_id, 32)} alt="" width={22} height={22} />
                </td>
                <td>{row.type_name}</td>
                <td>{fmtIsk(row.hub_buy)}</td>
                <td>{fmtIsk(row.hub_sell)}</td>
                <td>{fmtIsk(row.local_buy)}</td>
                <td>{fmtIsk(row.local_sell)}</td>
                <td>{row.spread_pct != null ? `${row.spread_pct}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CorpMarketOrderPanel({
  listings,
}: {
  listings: Awaited<ReturnType<typeof import("@/lib/api").fetchCorpMarket>>;
}) {
  const [buyerName, setBuyerName] = useState("");
  const [buyerId, setBuyerId] = useState("");
  const [typeName, setTypeName] = useState("");
  const [qty, setQty] = useState(1);
  const [unitPrice, setUnitPrice] = useState("");
  const [delivery, setDelivery] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const result = await submitCorpMarketOrder({
        buyer_character_name: buyerName.trim(),
        buyer_character_id: buyerId.trim() ? Number(buyerId) : undefined,
        type_name: typeName.trim(),
        quantity: qty,
        unit_price_isk: parseFloat(unitPrice),
        delivery_location: delivery.trim(),
        notes: notes.trim(),
      });
      setMessage(
        `Order #${result.id} submitted (${result.status}).` +
          (result.mail_sent_buyer || result.mail_sent_corp
            ? " EVE mail sent."
            : result.mail_error
              ? ` Mail: ${result.mail_error}`
              : "")
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      <StatusStrip>
        Order stock from us — EVE mail to you and staff with price, qty, and delivery location. Confirm in-game for contract.
      </StatusStrip>
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <label>
          Character name
          <input className="eve-input w-full mt-0.5" value={buyerName} onChange={(e) => setBuyerName(e.target.value)} />
        </label>
        <label>
          Character ID (for mail)
          <input className="eve-input w-full mt-0.5" value={buyerId} onChange={(e) => setBuyerId(e.target.value)} />
        </label>
        <label>
          Item name
          <input className="eve-input w-full mt-0.5" value={typeName} onChange={(e) => setTypeName(e.target.value)} />
        </label>
        <label>
          Qty
          <input
            className="eve-input w-full mt-0.5"
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
          />
        </label>
        <label>
          Unit price (ISK)
          <input className="eve-input w-full mt-0.5" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
        </label>
        <label>
          Delivery location
          <input className="eve-input w-full mt-0.5" value={delivery} onChange={(e) => setDelivery(e.target.value)} />
        </label>
      </div>
      <label className="text-[10px]">
        Notes
        <textarea className="eve-textarea w-full mt-0.5 min-h-[48px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button
        type="button"
        className="eve-btn eve-btn-primary self-start"
        disabled={loading || !buyerName.trim() || !typeName.trim() || !delivery.trim() || !unitPrice}
        onClick={submit}
      >
        {loading ? "Submitting…" : "Place order"}
      </button>
      {error ? <p className="text-[var(--danger)] text-[10px]">{error}</p> : null}
      {message ? <p className="text-[var(--ok)] text-[10px]">{message}</p> : null}
      <SectionHead>Available listings</SectionHead>
      <div className="overflow-auto flex-1">
        <table className="eve-table text-[10px]">
          <thead>
            <tr>
              <th />
              <th>Item</th>
              <th>Seller</th>
              <th>Qty</th>
              <th>Unit</th>
            </tr>
          </thead>
          <tbody>
            {listings.map((row) => (
              <tr key={row.id}>
                <td>
                  <img src={typeIconUrl(row.type_id, 32)} alt="" width={22} height={22} />
                </td>
                <td>{row.type_name}</td>
                <td>{row.seller_character_name}</td>
                <td>{row.quantity.toLocaleString()}</td>
                <td>{fmtIsk(row.unit_price_isk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HubToolLink({ slug, label, isPublic }: { slug: string; label: string; isPublic?: boolean }) {
  const { openWindow, focusWindow } = useWindowManager();
  const tool = TOOLS.find((t) => t.slug === slug);
  return (
    <button
      type="button"
      className="emums-tool-link text-left w-full"
      onClick={() => {
        if (!tool?.windowId) return;
        openToolInDesktop(slug, tool.windowId, openWindow, focusWindow);
      }}
    >
      {label}
      {isPublic ? <span className="emums-tool-badge">public</span> : null}
    </button>
  );
}

export function HubWorkspace({ hub, embedded }: { hub: ToolsHub; embedded?: boolean }) {
  const content = (
    <>
      <EveWindow id="tools-hub" title="Coalition Tool Hub" defaultX={40} defaultY={40} defaultWidth={720} defaultHeight={480}>
        <StatusStrip>EvE EMU | Edging Gone Wild — coalition tools framework</StatusStrip>
        <div className="emums-tool-grid">
          {hub.categories.map((cat) => (
            <div key={cat.slug} className="emums-tool-category">
              <SectionHead>{cat.label}</SectionHead>
              <ul className="emums-tool-list">
                {cat.tools.map((t) => (
                  <li key={t.slug}>
                    <HubToolLink slug={t.slug} label={t.label} isPublic={t.public} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </EveWindow>
      <EveWindow id="authed-structures" title="Authed Structures" defaultX={780} defaultY={40} defaultWidth={360} defaultHeight={280}>
        <SectionHead>Structure markets (SSO)</SectionHead>
        <ul className="text-[10px] space-y-1">
          {hub.authed_structures.map((s) => (
            <li key={s.structure_id} className="border-b border-[var(--border)] pb-1">
              <strong>{s.structure_name}</strong>
              <span className="text-[var(--text-muted)]"> — {s.system_name}</span>
              <div className="text-[9px] text-[var(--text-muted)]">
                {s.has_market ? "Market" : ""}
                {s.has_market && s.has_reprocessing ? " · " : ""}
                {s.has_reprocessing ? "Reprocessing" : ""}
              </div>
            </li>
          ))}
        </ul>
      </EveWindow>
      <EveWindow
        id="structure-fuel"
        title="Structure Fuel"
        defaultX={40}
        defaultY={340}
        defaultWidth={820}
        defaultHeight={480}
      >
        <StructureFuelPanel />
      </EveWindow>
    </>
  );
  if (embedded) return content;
  return <DesktopSurface className="min-h-0 flex-1">{content}</DesktopSurface>;
}

export function CommerceWorkspace({
  hub,
  corpMarket,
  embedded,
}: {
  hub: ToolsHub;
  corpMarket: Awaited<ReturnType<typeof import("@/lib/api").fetchCorpMarket>>;
  embedded?: boolean;
}) {
  const content = (
    <>
      <Suspense fallback={null}>
        <CommerceShareFocus />
      </Suspense>
      <EveWindow id="buyback" title="Buyback" defaultX={24} defaultY={24} defaultWidth={520} defaultHeight={520}>
        <Suspense fallback={null}>
          <PasteToolPanel mode="buyback" markets={hub.markets} structures={hub.authed_structures} />
        </Suspense>
      </EveWindow>
      <EveWindow id="appraisal" title="Appraisal" defaultX={560} defaultY={24} defaultWidth={520} defaultHeight={520}>
        <Suspense fallback={null}>
          <PasteToolPanel mode="appraisal" markets={hub.markets} structures={hub.authed_structures} />
        </Suspense>
      </EveWindow>
      <EveWindow id="refine-calc" title="Refine vs Sell" defaultX={300} defaultY={120} defaultWidth={560} defaultHeight={540}>
        <Suspense fallback={null}>
          <PasteToolPanel mode="refine" markets={hub.markets} structures={hub.authed_structures} />
        </Suspense>
      </EveWindow>
      <EveWindow id="market-watch" title="Market Tracker" defaultX={24} defaultY={560} defaultWidth={520} defaultHeight={320}>
        <MarketTrackerPanel markets={hub.markets} />
      </EveWindow>
      <EveWindow id="corp-market" title="Corp Market" defaultX={560} defaultY={560} defaultWidth={520} defaultHeight={320}>
        <CorpMarketOrderPanel listings={corpMarket} />
      </EveWindow>
    </>
  );
  if (embedded) {
    return (
      <>
        <Suspense fallback={null}>
          <CommerceShareFocus />
        </Suspense>
        {content}
      </>
    );
  }
  return (
    <DesktopSurface className="min-h-0 flex-1">
      <Suspense fallback={null}>
        <CommerceShareFocus />
      </Suspense>
      {content}
    </DesktopSurface>
  );
}

export function IntelligenceWorkspace({
  killboard,
  routes,
  embedded,
}: {
  killboard: Awaited<ReturnType<typeof import("@/lib/api").fetchKillboard>>;
  routes: Awaited<ReturnType<typeof import("@/lib/api").fetchRoutes>>;
  embedded?: boolean;
}) {
  const { openWindow, focusWindow } = useWindowManager();
  const [sdeTypeId, setSdeTypeId] = useState<number | null>(null);
  const [sdeTitle, setSdeTitle] = useState("Item details");
  const [shipNode, setShipNode] = useState<AssetTreeNode | null>(null);
  const [shipLocation, setShipLocation] = useState("");
  const [shipTitle, setShipTitle] = useState("Ship fitting");
  const [systemId, setSystemId] = useState<number | null>(null);
  const [systemTitle, setSystemTitle] = useState("System details");
  const [wikiTitle, setWikiTitle] = useState<string | null>(null);
  const [wikiWindowTitle, setWikiWindowTitle] = useState("Wiki article");

  const openOrgWiki = useCallback(
    (title: string, displayName: string) => {
      setWikiTitle(title);
      setWikiWindowTitle(displayName);
      openWindow("char-org-wiki");
      focusWindow("char-org-wiki");
    },
    [openWindow, focusWindow]
  );

  useEffect(() => {
    const onInspect = (ev: Event) => {
      const cid = (ev as CustomEvent<{ character_id?: number }>).detail?.character_id;
      if (!cid) return;
      openWindow("char-audit");
      focusWindow("char-audit");
    };
    window.addEventListener("emums:inspect-character", onInspect);
    return () => window.removeEventListener("emums:inspect-character", onInspect);
  }, [openWindow, focusWindow]);

  const intelWindows = (
    <>
      <EveWindow id="char-audit" title="Character Sheet" defaultX={20} defaultY={20} defaultWidth={640} defaultHeight={520}>
        <CharacterSheetPanel />
      </EveWindow>
      <EveWindow
        id="interaction-audit"
        title="Interaction Audit"
        defaultX={40}
        defaultY={60}
        defaultWidth={720}
        defaultHeight={520}
      >
        <InteractionAuditPanel />
      </EveWindow>
      <EveWindow
        id="webhook-alerts"
        title="Webhook Notifications"
        defaultX={60}
        defaultY={80}
        defaultWidth={640}
        defaultHeight={520}
      >
        <WebhookNotificationPanel />
      </EveWindow>
      <EveWindow
        id="pi-overview"
        title="Planetary Interaction"
        defaultX={80}
        defaultY={100}
        defaultWidth={760}
        defaultHeight={540}
      >
        <PiOverviewPanel />
      </EveWindow>
      <EveWindow id="char-item-detail" title={sdeTitle} defaultX={680} defaultY={20} defaultWidth={420} defaultHeight={480}>
        <SdeItemDetailPanel typeId={sdeTypeId} />
      </EveWindow>
      <EveWindow id="char-ship-fitting" title={shipTitle} defaultX={680} defaultY={320} defaultWidth={440} defaultHeight={400}>
        <AssetShipFittingPanel ship={shipNode} locationName={shipLocation} />
      </EveWindow>
      <EveWindow id="char-system-detail" title={systemTitle} defaultX={680} defaultY={120} defaultWidth={360} defaultHeight={320}>
        <SystemDetailPanel systemId={systemId} />
      </EveWindow>
      <EveWindow id="char-org-wiki" title={wikiWindowTitle} defaultX={680} defaultY={460} defaultWidth={480} defaultHeight={420}>
        <WikiArticlePanel
          title={wikiTitle}
          onOpenWiki={(title) => {
            setWikiTitle(title);
            setWikiWindowTitle(title.split("/").pop() || title);
          }}
        />
      </EveWindow>
      <EveWindow id="killboard" title="Killboard" defaultX={520} defaultY={20} defaultWidth={620} defaultHeight={560}>
        <KillboardPanel initialRows={killboard} />
      </EveWindow>
      <EveWindow id="route-planner" title="Route Planner" defaultX={560} defaultY={440} defaultWidth={480} defaultHeight={360}>
        <SectionHead>Saved routes (Dotlan / e-route style)</SectionHead>
        <ul className="text-[10px] space-y-2">
          {routes.map((r) => (
            <li key={r.id} className="border border-[var(--border)] p-2">
              <strong>{r.name}</strong>
              <div>
                {r.origin_system} → {r.destination_system} · {r.jumps} jumps · max sec {r.security_max}
              </div>
            </li>
          ))}
        </ul>
      </EveWindow>
    </>
  );

  return (
    <CharSheetInspectProvider
      onOpenItemWindow={(typeId, name) => {
        setSdeTypeId(typeId);
        setSdeTitle(name);
        openWindow("char-item-detail");
        focusWindow("char-item-detail");
      }}
      onOpenShipWindow={(ship, locationName) => {
        setShipNode(ship);
        setShipLocation(locationName);
        setShipTitle(ship.custom_name || ship.type_name);
        openWindow("char-ship-fitting");
        focusWindow("char-ship-fitting");
      }}
      onOpenSystemWindow={(sid, name) => {
        setSystemId(sid);
        setSystemTitle(name);
        openWindow("char-system-detail");
        focusWindow("char-system-detail");
      }}
      onOpenWikiWindow={openOrgWiki}
    >
      {embedded ? intelWindows : <DesktopSurface className="min-h-0 flex-1">{intelWindows}</DesktopSurface>}
    </CharSheetInspectProvider>
  );
}

export function AdministrationWorkspace({
  services,
  ratting,
  leaves,
  pni,
  srp,
}: {
  services: Awaited<ReturnType<typeof import("@/lib/api").fetchServiceLinks>>;
  ratting: Awaited<ReturnType<typeof import("@/lib/api").fetchRattingPeriods>>;
  leaves: Awaited<ReturnType<typeof import("@/lib/api").fetchHrLeaves>>;
  pni: Awaited<ReturnType<typeof import("@/lib/api").fetchPniStatements>>;
  srp: Awaited<ReturnType<typeof import("@/lib/api").fetchSrpLosses>>;
}) {
  return (
    <WindowDesktop className="min-h-0 flex-1">
      <EveWindow id="services" title="Service Links" defaultX={20} defaultY={20} defaultWidth={360} defaultHeight={320}>
        <ul className="text-[10px] space-y-2">
          {services.map((s) => (
            <li key={s.id}>
              <a href={s.url} className="text-[var(--link)] font-semibold" target="_blank" rel="noreferrer">
                {s.label}
              </a>
              <div className="text-[var(--text-muted)]">{s.description}</div>
            </li>
          ))}
        </ul>
      </EveWindow>
      <EveWindow id="ratting-tax" title="Ratting Tax" defaultX={400} defaultY={20} defaultWidth={400} defaultHeight={320}>
        {ratting.map((p) => (
          <div key={p.id} className="border-b border-[var(--border)] py-2 text-[10px]">
            <strong>{p.period_label}</strong> · {p.rate_pct}% · {p.status}
            <div>Bounty: {fmtIsk(p.total_bounty_isk)} · Collected: {fmtIsk(p.total_collected_isk)}</div>
          </div>
        ))}
      </EveWindow>
      <EveWindow id="hr-directorate" title="HR Directorate" defaultX={820} defaultY={20} defaultWidth={380} defaultHeight={320}>
        <SectionHead>Leave of absence</SectionHead>
        <ul className="text-[10px] mb-2">
          {leaves.map((l) => (
            <li key={l.id}>
              {l.character_name}: {l.start_date} → {l.end_date} ({l.status})
            </li>
          ))}
        </ul>
        <SectionHead>Account flags & blacklist</SectionHead>
        <p className="text-[9px] text-[var(--text-muted)]">Admin-configurable flags sync from HR backend.</p>
      </EveWindow>
      <EveWindow id="pni-statements" title="P&I Statements" defaultX={20} defaultY={360} defaultWidth={480} defaultHeight={280}>
        {pni.map((s) => (
          <div key={s.id} className="text-[10px] py-2 border-b border-[var(--border)]">
            <strong>{s.period_label}</strong> · {s.status}
            <div>Income {fmtIsk(s.total_income_isk)} · Expense {fmtIsk(s.total_expense_isk)}</div>
          </div>
        ))}
      </EveWindow>
      <EveWindow id="srp-program" title="SRP Program" defaultX={520} defaultY={360} defaultWidth={900} defaultHeight={420}>
        <SrpProgramPanel />
      </EveWindow>
    </WindowDesktop>
  );
}

export { toolsForCategory, TOOLS };
