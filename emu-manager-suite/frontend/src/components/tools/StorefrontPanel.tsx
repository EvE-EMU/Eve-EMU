"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { SectionHead, StatusStrip } from "@/components/ui";
import { CharSheetSortButton } from "@/components/tools/CharSheetTableToolbar";
import { typeIconUrl } from "@/lib/evetech";
import { sortByKey, useTableSort } from "@/lib/useTableSort";
import type { StorefrontCatalog, StorefrontCatalogItem } from "@/lib/api";

function fmtIsk(v: number | null | undefined) {
  if (v == null) return "Contact";
  return `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })} ISK`;
}

function priceSourceLabel(source: string) {
  switch (source) {
    case "override":
      return "override";
    case "janice_split":
      return "split";
    case "janice_sell":
    case "market_sell":
      return "sell";
    case "janice_buy":
    case "market_buy":
      return "buy";
    case "components":
      return "kit parts";
    case "manual":
      return "manual";
    default:
      return source || "—";
  }
}

export function StorefrontPanel({
  catalog: initialCatalog,
  highlightTypeId,
}: {
  catalog: StorefrontCatalog;
  highlightTypeId?: number | null;
}) {
  const [catalog, setCatalog] = useState(initialCatalog);
  const [cart, setCart] = useState<Record<string, number>>(() => {
    if (typeof window === "undefined") return {};
    try {
      const raw = sessionStorage.getItem("emums_storefront_cart");
      return raw ? (JSON.parse(raw) as Record<string, number>) : {};
    } catch {
      return {};
    }
  });
  const [pickupId, setPickupId] = useState<number | "">(
    initialCatalog.pickup_locations.find((l) => l.is_default)?.id ??
      initialCatalog.pickup_locations[0]?.id ??
      ""
  );
  const [notes, setNotes] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [kindFilter, setKindFilter] = useState<"all" | "item" | "kit">("all");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [orderResult, setOrderResult] = useState<Record<string, unknown> | null>(null);
  const [expandedKit, setExpandedKit] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [myOrders, setMyOrders] = useState<
    { order_code: string; total_isk: number; status: string; created_at: string | null; pickup_label: string }[]
  >([]);

  useEffect(() => {
    try {
      sessionStorage.setItem("emums_storefront_cart", JSON.stringify(cart));
    } catch {
      /* ignore */
    }
  }, [cart]);

  const loadMyOrders = useCallback(async () => {
    try {
      const res = await fetch("/api/tools/storefront/my-orders", { cache: "no-store" });
      if (!res.ok) {
        setMyOrders([]);
        return;
      }
      const data = await res.json();
      setMyOrders(data.orders || []);
    } catch {
      setMyOrders([]);
    }
  }, []);

  useEffect(() => {
    void loadMyOrders();
  }, [loadMyOrders]);
  type SortKey = "name" | "stock" | "price" | "category";
  const { sortKey, sortAsc, toggleSort } = useTableSort<SortKey>("name", true);

  useEffect(() => {
    setCatalog(initialCatalog);
  }, [initialCatalog]);

  const refreshCatalog = useCallback(async () => {
    setRefreshing(true);
    setError("");
    try {
      const res = await fetch("/api/tools/storefront", { cache: "no-store" });
      if (!res.ok) throw new Error("Refresh failed");
      const data = (await res.json()) as StorefrontCatalog;
      setCatalog(data);
      if (!pickupId && data.pickup_locations.length) {
        setPickupId(data.pickup_locations.find((l) => l.is_default)?.id ?? data.pickup_locations[0].id);
      }
    } catch {
      setError("Could not refresh catalog.");
    } finally {
      setRefreshing(false);
    }
  }, [pickupId]);

  useEffect(() => {
    const t = window.setInterval(() => {
      void refreshCatalog();
    }, 90_000);
    return () => window.clearInterval(t);
  }, [refreshCatalog]);

  const categories = useMemo(() => {
    const fromSummary = catalog.summary?.categories;
    if (fromSummary?.length) return fromSummary;
    return sortedUnique(catalog.items.map((i) => i.category_name || "Other"));
  }, [catalog]);

  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return catalog.items.filter((i) => {
      if (i.hidden || i.quantity <= 0) return false;
      if (kindFilter !== "all" && i.kind !== kindFilter) return false;
      if (category !== "all" && (i.category_name || "Other") !== category) return false;
      if (!q) return true;
      return (
        i.name.toLowerCase().includes(q) ||
        (i.group_name || "").toLowerCase().includes(q) ||
        (i.note || "").toLowerCase().includes(q) ||
        String(i.type_id || "").includes(q)
      );
    });
  }, [catalog.items, search, category, kindFilter]);

  const sortedItems = useMemo(
    () =>
      sortByKey(visibleItems, sortKey, sortAsc, (row, key) => {
        if (key === "name") return row.name;
        if (key === "stock") return row.quantity;
        if (key === "category") return row.category_name || "Other";
        return row.unit_price_isk ?? -1;
      }),
    [visibleItems, sortKey, sortAsc]
  );

  const cartLines = useMemo(() => {
    return Object.entries(cart)
      .filter(([, qty]) => qty > 0)
      .map(([key, qty]) => {
        const item = catalog.items.find((i) => i.key === key);
        return item ? { item, qty } : null;
      })
      .filter(Boolean) as { item: StorefrontCatalogItem; qty: number }[];
  }, [cart, catalog.items]);

  const cartTotal = useMemo(
    () =>
      cartLines.reduce((sum, { item, qty }) => {
        if (item.unit_price_isk == null) return sum;
        return sum + item.unit_price_isk * qty;
      }, 0),
    [cartLines]
  );

  const hasUnpriced = cartLines.some(({ item }) => item.unit_price_isk == null);
  const overStock = cartLines.some(({ item, qty }) => qty > item.quantity);

  const setQty = (key: string, qty: number, max?: number) => {
    setCart((prev) => {
      const next = { ...prev };
      const capped = max != null ? Math.min(qty, max) : qty;
      if (capped <= 0) delete next[key];
      else next[key] = capped;
      return next;
    });
  };

  const submitOrder = useCallback(async () => {
    setLoading(true);
    setError("");
    setOrderResult(null);
    try {
      const res = await fetch("/api/tools/storefront/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pickup_location_id: pickupId || null,
          lines: cartLines.map(({ item, qty }) => ({ key: item.key, quantity: qty })),
          notes,
        }),
      });
      const data = (await res.json()) as Record<string, unknown>;
      if (!res.ok) {
        setError(String(data.detail || data.message || "Order failed"));
        return;
      }
      setOrderResult(data);
      setCart({});
      setNotes("");
      void refreshCatalog();
      void loadMyOrders();
    } catch {
      setError("Could not submit order — log in with SSO to checkout.");
    } finally {
      setLoading(false);
    }
  }, [cartLines, notes, pickupId, refreshCatalog, loadMyOrders]);

  const copyOrderCode = async () => {
    const code = String(orderResult?.order_code || orderResult?.contract_description || "");
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  const summary = catalog.summary;
  const pickup = catalog.pickup_locations.find((l) => l.id === pickupId);

  return (
    <div className="storefront-panel flex flex-col gap-2 min-h-0 h-full">
      <StatusStrip>
        <strong>{catalog.corp_name}</strong> · {catalog.pricing_source}
        {!catalog.enabled ? " · DISABLED" : ""}
        {summary
          ? ` · ${summary.item_count} listings · ${summary.priced_count} priced · ${summary.total_stock_units.toLocaleString()} units`
          : ""}
        {typeof catalog.inventory_source.sync_character_count === "number"
          ? ` · ${catalog.inventory_source.sync_character_count} stock alt(s)`
          : ""}
      </StatusStrip>

      <div className="flex flex-wrap gap-2 items-end text-[11px]">
        <label className="flex-1 min-w-[140px]">
          Search
          <input
            className="eve-input w-full mt-0.5"
            placeholder="Name, group, type id…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label>
          Category
          <select className="eve-select ml-1" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="all">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Kind
          <select
            className="eve-select ml-1"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as typeof kindFilter)}
          >
            <option value="all">All</option>
            <option value="item">Items</option>
            <option value="kit">Kits</option>
          </select>
        </label>
        <button
          type="button"
          className="eve-btn eve-btn-secondary text-sm"
          onClick={() => void refreshCatalog()}
          disabled={refreshing}
        >
          {refreshing ? "Refreshing…" : "Refresh stock"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-2 min-h-0 flex-1">
        <div className="overflow-auto min-h-0 border border-[var(--edge-dim)]">
          <table className="eve-table">
            <thead>
              <tr>
                <th />
                <th>
                  <CharSheetSortButton label="Item" active={sortKey === "name"} asc={sortAsc} onClick={() => toggleSort("name")} />
                </th>
                <th>
                  <CharSheetSortButton
                    label="Category"
                    active={sortKey === "category"}
                    asc={sortAsc}
                    onClick={() => toggleSort("category")}
                  />
                </th>
                <th className="text-right">
                  <CharSheetSortButton label="Stock" active={sortKey === "stock"} asc={sortAsc} onClick={() => toggleSort("stock")} align="right" />
                </th>
                <th className="text-right">
                  <CharSheetSortButton label="Price" active={sortKey === "price"} asc={sortAsc} onClick={() => toggleSort("price")} align="right" />
                </th>
                <th className="text-right">Cart</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((row) => {
                const selected = highlightTypeId != null && row.type_id === highlightTypeId;
                const inCart = cart[row.key] ?? 0;
                const priced = row.unit_price_isk != null;
                return (
                  <tr key={row.key} className={selected ? "eve-row-selected" : undefined}>
                    <td>
                      {row.type_id ? (
                        <img src={typeIconUrl(row.type_id, 32)} alt="" width={24} height={24} />
                      ) : (
                        <span title="Kit">📦</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="text-left hover:underline"
                        onClick={() =>
                          row.kind === "kit" ? setExpandedKit(expandedKit === row.key ? null : row.key) : undefined
                        }
                      >
                        <strong>{row.name}</strong>
                        {row.kind === "kit" ? (
                          <span className="text-[var(--text-muted)] ml-1">(kit)</span>
                        ) : null}
                        {row.low_stock ? (
                          <span className="ml-1 text-[var(--warn)] text-[9px]">low</span>
                        ) : null}
                      </button>
                      {row.group_name ? (
                        <div className="text-[9px] text-[var(--text-muted)]">{row.group_name}</div>
                      ) : null}
                      {expandedKit === row.key && row.kit_items.length ? (
                        <ul className="text-[9px] text-[var(--text-muted)] mt-0.5 pl-2">
                          {row.kit_items.map((k) => (
                            <li key={`${k.type_id}-${k.quantity}`}>
                              {k.type_name} ×{k.quantity.toLocaleString()}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {row.note ? <div className="text-[9px] text-[var(--text-muted)]">{row.note}</div> : null}
                    </td>
                    <td className="text-[10px] text-[var(--text-muted)]">{row.category_name || "—"}</td>
                    <td className="num">{row.quantity.toLocaleString()}</td>
                    <td className="num text-[var(--warn)]">
                      {fmtIsk(row.unit_price_isk)}
                      <div className="text-[8px] text-[var(--text-muted)]">{priceSourceLabel(row.price_source)}</div>
                    </td>
                    <td className="num">
                      {priced ? (
                        <div className="inline-flex items-center gap-0.5">
                          <button
                            type="button"
                            className="eve-btn eve-btn-secondary px-1 py-0 text-[10px]"
                            onClick={() => setQty(row.key, inCart - 1, row.quantity)}
                            disabled={inCart <= 0}
                          >
                            −
                          </button>
                          <input
                            className="eve-input w-12 text-right"
                            type="number"
                            min={0}
                            max={row.quantity}
                            value={inCart || ""}
                            placeholder="0"
                            onChange={(e) => setQty(row.key, parseInt(e.target.value, 10) || 0, row.quantity)}
                          />
                          <button
                            type="button"
                            className="eve-btn eve-btn-secondary px-1 py-0 text-[10px]"
                            onClick={() => setQty(row.key, inCart + 1, row.quantity)}
                            disabled={inCart >= row.quantity}
                          >
                            +
                          </button>
                          <button
                            type="button"
                            className="eve-btn eve-btn-secondary px-1 py-0 text-[10px]"
                            title="Max stock"
                            onClick={() => setQty(row.key, row.quantity, row.quantity)}
                          >
                            max
                          </button>
                        </div>
                      ) : (
                        <span className="text-[var(--text-muted)]">Contact</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!sortedItems.length ? (
            <p className="p-3 text-sm text-[var(--text-muted)]">
              {catalog.items.length
                ? "No items match your filters."
                : "No stock listed — link a corp SSO alt with corporation assets scope and run audit sync."}
            </p>
          ) : null}
        </div>

        <div className="border border-[var(--edge-dim)] p-2 text-[10px] flex flex-col gap-2 min-h-0">
          <div className="flex items-center justify-between gap-1">
            <SectionHead>Cart ({cartLines.length})</SectionHead>
            {cartLines.length ? (
              <button type="button" className="eve-btn eve-btn-secondary text-[10px] py-0" onClick={() => setCart({})}>
                Clear
              </button>
            ) : null}
          </div>
          {cartLines.length ? (
            <ul className="space-y-1 max-h-[180px] overflow-auto">
              {cartLines.map(({ item, qty }) => {
                const line = item.unit_price_isk != null ? item.unit_price_isk * qty : null;
                const over = qty > item.quantity;
                return (
                  <li key={item.key} className="flex gap-1 items-start">
                    {item.type_id ? <EveTypeIcon typeId={item.type_id} size={16} /> : null}
                    <div className="flex-1 min-w-0">
                      <div className="truncate">{item.name}</div>
                      <div className={over ? "text-[var(--danger)]" : "text-[var(--text-muted)]"}>
                        ×{qty}
                        {over ? ` (only ${item.quantity} in stock)` : ""} · {fmtIsk(line)}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="eve-btn eve-btn-secondary px-1 py-0"
                      onClick={() => setQty(item.key, 0)}
                      title="Remove"
                    >
                      ×
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-[var(--text-muted)]">Add quantities from the catalog.</p>
          )}
          <div className="font-medium text-[12px]">
            Total: {hasUnpriced || !cartLines.length ? "—" : fmtIsk(cartTotal)}
          </div>
          <label>
            Pickup
            <select
              className="eve-select w-full mt-0.5"
              value={pickupId}
              onChange={(e) => setPickupId(e.target.value ? Number(e.target.value) : "")}
            >
              {!catalog.pickup_locations.length ? <option value="">No locations</option> : null}
              {catalog.pickup_locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.label}
                  {loc.system_name ? ` — ${loc.system_name}` : ""}
                </option>
              ))}
            </select>
          </label>
          {pickup?.location_hint ? (
            <p className="text-[9px] text-[var(--text-muted)]">{pickup.location_hint}</p>
          ) : null}
          <label>
            Notes for staff
            <textarea
              className="eve-input w-full mt-0.5 h-12"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional delivery notes"
            />
          </label>
          <button
            type="button"
            className="eve-btn eve-btn-primary text-sm"
            disabled={
              loading ||
              !cartLines.length ||
              hasUnpriced ||
              overStock ||
              !catalog.enabled ||
              !catalog.pickup_locations.length
            }
            onClick={() => void submitOrder()}
          >
            {loading ? "Submitting…" : "Confirm order (WTB contract)"}
          </button>
          <p className="text-[var(--text-muted)] text-[9px]">
            You get EVE mail with steps. Create an Item Exchange WTB to <strong>{catalog.corp_name}</strong> using the
            order code.
          </p>
          {error ? <p className="text-[var(--danger)]">{error}</p> : null}
          {overStock ? <p className="text-[var(--danger)]">Reduce quantities — cart exceeds stock.</p> : null}

          {myOrders.length ? (
            <div className="border-t border-[var(--edge-dim)] pt-2 mt-1">
              <SectionHead>My recent orders</SectionHead>
              <ul className="space-y-1 max-h-28 overflow-auto">
                {myOrders.slice(0, 8).map((o) => (
                  <li key={o.order_code} className="flex justify-between gap-1">
                    <span className="font-mono">{o.order_code}</span>
                    <span className="text-[var(--text-muted)]">{o.status}</span>
                    <span className="num">{fmtIsk(o.total_isk)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      {orderResult ? (
        <div className="border border-[var(--accent)] p-2 text-[10px] bg-[var(--panel-inset)]">
          <div className="flex flex-wrap items-center gap-2">
            <strong>Order {String(orderResult.order_code)}</strong>
            <button type="button" className="eve-btn eve-btn-secondary text-[10px] py-0" onClick={() => void copyOrderCode()}>
              {copied ? "Copied" : "Copy code"}
            </button>
          </div>
          <p className="text-[var(--text-muted)] mt-1">
            Total {fmtIsk(orderResult.total_isk as number)} ·{" "}
            {orderResult.mail_sent_buyer ? "Buyer mail sent." : "Buyer mail pending."}
            {orderResult.discord_sent ? " Staff notified on Discord." : ""}
            {orderResult.mail_error ? ` (${String(orderResult.mail_error)})` : ""}
          </p>
          {orderResult.contract_instructions ? (
            <div className="mt-1">
              <SectionHead>WTB contract steps</SectionHead>
              <ol className="list-decimal pl-4 space-y-0.5">
                {((orderResult.contract_instructions as { steps?: string[] }).steps ?? []).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <p className="mt-1 font-mono text-[11px] select-all">{String(orderResult.contract_description)}</p>
            </div>
          ) : null}
          {(() => {
            const bridge = orderResult.mfg_bridge as
              | { industrial_url?: string; ok?: boolean; code?: string }
              | undefined;
            const url =
              (typeof orderResult.industrial_url === "string" && orderResult.industrial_url) ||
              bridge?.industrial_url ||
              (bridge?.code
                ? `https://eve-emu.com/industrial/projects/${bridge.code}`
                : "https://eve-emu.com/industrial?tab=projects");
            return (
              <p className="mt-2 text-[11px] text-[var(--text-muted)]">
                {bridge?.ok
                  ? "Bridged to ManufacturingProject / ProjectQuote — "
                  : "Track orders on the canonical industrial suite — "}
                <a className="text-[var(--accent)] underline" href={url} target="_blank" rel="noreferrer">
                  open eve-emu.com/industrial
                </a>
              </p>
            );
          })()}
        </div>
      ) : null}
    </div>
  );
}

function sortedUnique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}
