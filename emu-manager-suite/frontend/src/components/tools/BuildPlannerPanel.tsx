"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EveRadarChart } from "@/components/EveRadarChart";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { KpiStrip, KpiTile, SectionHead } from "@/components/ui";
import { blueprintScrollIconUrl, typeRenderUrl } from "@/lib/evetech";
import { shipRadarFromAttributes } from "@/lib/shipRadarStats";

type FittingRow = {
  id: number;
  name: string;
  ship_type_id: number;
  ship_type_name: string;
  owner_character_name?: string;
};

type BlueprintRow = {
  id: number;
  type_id: number;
  type_name: string;
  material_efficiency: number;
  time_efficiency: number;
  runs: number;
  owner_character_name?: string;
};

type StructureRow = {
  structure_id: number;
  structure_name: string;
  system_name: string;
  location_label?: string;
};

export type ProductionPlan = {
  plan_code?: string;
  source_name?: string;
  error?: string;
  message?: string;
  runs?: number;
  material_mode?: string;
  me?: number;
  te?: number;
  structure?: StructureRow & {
    material_bonus_pct?: number;
    time_bonus_pct?: number;
    tax_pct?: number;
  };
  cash_flow?: {
    starting_stocks_buy: number;
    starting_stocks_sell: number;
    end_stocks_buy: number;
    end_stocks_sell: number;
    materials_to_buy_buy: number;
    materials_to_buy_sell: number;
    manufacturing_job_costs: number;
    total_sales_taxes: number;
    invention_cost: number;
    end_products_buy: number;
    end_products_sell: number;
    expected_profit: number;
  };
  job_time?: { end_products_seconds: number; total_seconds: number; total_days: number };
  materials?: MaterialLine[];
  end_products?: {
    type_id: number;
    name: string;
    amount: number;
    volume_m3: number;
    sell_unit_price: number;
    sell_total: number;
  }[];
  jobs?: JobLine[];
  produced_parts?: { name: string; runs: number; time_seconds: number }[];
  buy_list?: { type_id: number; name: string; quantity: number; unit_price: number; total_isk: number }[];
  stock_available?: Record<string, number>;
  price_hub?: string;
  price_hub_label?: string;
  pricing_source?: string;
  janice_configured?: boolean;
  janice_buy_appraisal?: { code: string; url: string } | null;
};

type MaterialLine = {
  type_id: number;
  name: string;
  required_qty: number;
  to_buy: number;
  to_buy_buy_value: number;
  to_buy_sell_value: number;
  volume_m3: number;
  start_amount: number;
  buy_unit_price: number;
  sell_unit_price: number;
  in_stock: number;
  is_component: boolean;
};

type JobLine = {
  name: string;
  runs: number;
  me: number;
  days: number;
  job_cost: number;
  product_name?: string;
  is_end_product?: boolean;
};

function fmtIsk(v: number | string | null | undefined) {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function FittingShipRadar({ typeId }: { typeId: number }) {
  const [radar, setRadar] = useState<ReturnType<typeof shipRadarFromAttributes>>([]);

  useEffect(() => {
    if (!typeId) return;
    fetch(`/api/tools/sde/types/${typeId}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.attributes) setRadar(shipRadarFromAttributes(data.attributes));
      })
      .catch(() => setRadar([]));
  }, [typeId]);

  if (radar.length < 3) return null;
  return (
    <div className="px-2 pb-2 border-b border-[var(--edge-dim)]">
      <EveRadarChart data={radar} title="Ship combat profile" compact />
    </div>
  );
}

type PlannerSource =
  | { kind: "fitting"; id: number; label: string; typeId: number }
  | { kind: "blueprint"; id: number; label: string; typeId: number };

export function BuildPlannerPanel({
  fittings,
  blueprints,
  structures,
  projects: projectsProp = [],
  onSync,
  syncing,
  syncError,
  focusBlueprintId,
  onFocusBlueprintHandled,
}: {
  fittings: FittingRow[];
  blueprints: BlueprintRow[];
  structures: StructureRow[];
  projects?: { id: number; name: string; container_name?: string }[];
  onSync: () => void;
  syncing: boolean;
  syncError: string | null;
  focusBlueprintId?: number | null;
  onFocusBlueprintHandled?: () => void;
}) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [plan, setPlan] = useState<ProductionPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [runs, setRuns] = useState(1);
  const [materialMode, setMaterialMode] = useState<"base" | "components">("base");
  const [structureId, setStructureId] = useState<number | "">("");
  const [locationFilter, setLocationFilter] = useState<"all" | "stock" | "station">("all");
  const [stationName, setStationName] = useState("");
  const [priceOverrides, setPriceOverrides] = useState<Record<number, string>>({});
  const [stockAssignments, setStockAssignments] = useState<Record<number, string>>({});
  const [useMaxStock, setUseMaxStock] = useState(true);
  const [projectId, setProjectId] = useState<number | "">("");
  const [containerName, setContainerName] = useState("");
  const [newFitName, setNewFitName] = useState("");
  const [newFitTypeId, setNewFitTypeId] = useState("");
  const [localFittings, setLocalFittings] = useState(fittings);

  const projects = useMemo(
    () =>
      projectsProp.map((r) => ({
        id: r.id,
        name: r.name,
        container_name: r.container_name || "",
      })),
    [projectsProp]
  );

  useEffect(() => {
    setLocalFittings(fittings);
  }, [fittings]);

  const sources: PlannerSource[] = useMemo(
    () => [
      ...localFittings.map((f) => ({
        kind: "fitting" as const,
        id: f.id,
        label: `${f.name} — ${f.ship_type_name}`,
        typeId: f.ship_type_id,
      })),
      ...blueprints.map((b) => ({
        kind: "blueprint" as const,
        id: b.id,
        label: b.type_name,
        typeId: b.type_id,
      })),
    ],
    [localFittings, blueprints]
  );

  const runPlan = useCallback(
    async (source: PlannerSource) => {
      setPlanLoading(true);
      setPlanError(null);
      setExpandedKey(`${source.kind}:${source.id}`);
      const overrides: Record<number, number> = {};
      for (const [k, v] of Object.entries(priceOverrides)) {
        const n = parseFloat(v);
        if (!Number.isNaN(n)) overrides[Number(k)] = n;
      }
      const stock: Record<number, number> = {};
      for (const [k, v] of Object.entries(stockAssignments)) {
        const n = parseInt(v, 10);
        if (!Number.isNaN(n)) stock[Number(k)] = n;
      }
      try {
        const res = await fetch("/api/tools/industrial-planning/calculate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_type: source.kind,
            source_id: source.id,
            runs,
            material_mode: materialMode,
            location_filter: locationFilter,
            station_name: locationFilter === "station" ? stationName : null,
            structure_id: structureId || null,
            price_hub: "jita",
            price_overrides: overrides,
            stock_assignments: stock,
            use_max_stock: useMaxStock,
            project_id: projectId || null,
            container_name: containerName.trim() || null,
          }),
        });
        const data = (await res.json()) as ProductionPlan;
        if (!res.ok || data.error) {
          setPlan(null);
          setPlanError(data.message || data.error || "Plan failed");
          return;
        }
        setPlan(data);
      } catch {
        setPlanError("Could not calculate production plan.");
        setPlan(null);
      } finally {
        setPlanLoading(false);
      }
    },
    [
      runs,
      materialMode,
      locationFilter,
      stationName,
      structureId,
      priceOverrides,
      stockAssignments,
      useMaxStock,
      projectId,
      containerName,
    ]
  );

  useEffect(() => {
    if (!focusBlueprintId) return;
    const bp = blueprints.find((b) => b.id === focusBlueprintId);
    if (!bp) return;
    void runPlan({
      kind: "blueprint",
      id: bp.id,
      label: bp.type_name,
      typeId: bp.type_id,
    });
    onFocusBlueprintHandled?.();
  }, [focusBlueprintId, blueprints, onFocusBlueprintHandled, runPlan]);

  const addFitting = useCallback(async () => {
    const tid = parseInt(newFitTypeId, 10);
    if (!newFitName.trim() || !tid) return;
    const res = await fetch("/api/tools/industry/fittings/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newFitName.trim(), ship_type_id: tid }),
    });
    if (!res.ok) return;
    const row = (await res.json()) as FittingRow;
    setLocalFittings((prev) => [row, ...prev]);
    setNewFitName("");
    setNewFitTypeId("");
  }, [newFitName, newFitTypeId]);

  const copyBuyList = useCallback(() => {
    if (!plan?.buy_list?.length) return;
    const text = plan.buy_list
      .map((r) => `${r.name}\t${r.quantity}\t${Math.round(r.unit_price)}`)
      .join("\n");
    void navigator.clipboard.writeText(text);
  }, [plan]);

  return (
    <div className="build-planner flex flex-col min-h-0 h-full">
      <div className="flex flex-wrap gap-2 mb-2 items-center">
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={onSync} disabled={syncing}>
          {syncing ? "Syncing…" : "Sync from game"}
        </button>
        {syncError ? <span className="text-[var(--danger)] text-sm">{syncError}</span> : null}
      </div>

      <div className="flex flex-wrap gap-2 mb-2 items-end text-[11px]">
        <label>
          Runs
          <input
            className="eve-input w-16 ml-1"
            type="number"
            min={1}
            value={runs}
            onChange={(e) => setRuns(Math.max(1, parseInt(e.target.value, 10) || 1))}
          />
        </label>
        <label>
          Materials
          <select
            className="eve-select ml-1"
            value={materialMode}
            onChange={(e) => setMaterialMode(e.target.value as "base" | "components")}
          >
            <option value="base">Base materials (minerals/PI)</option>
            <option value="components">Build components</option>
          </select>
        </label>
        <label>
          Stock filter
          <select
            className="eve-select ml-1"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value as typeof locationFilter)}
          >
            <option value="all">All hangars</option>
            <option value="stock">Stock locations</option>
            <option value="station">Station name</option>
          </select>
        </label>
        {locationFilter === "station" ? (
          <input
            className="eve-input w-32"
            placeholder="Station…"
            value={stationName}
            onChange={(e) => setStationName(e.target.value)}
          />
        ) : null}
        <label>
          Build at
          <select
            className="eve-select ml-1 max-w-[180px]"
            value={structureId}
            onChange={(e) => setStructureId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">Best configured</option>
            {structures.map((s) => (
              <option key={s.structure_id} value={s.structure_id}>
                {s.structure_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Project warehouse
          <select
            className="eve-select ml-1 max-w-[200px]"
            value={projectId}
            onChange={(e) => {
              const id = e.target.value ? Number(e.target.value) : "";
              setProjectId(id);
              if (id) {
                const p = projects.find((row) => row.id === id);
                if (p?.container_name) setContainerName(p.container_name);
              }
            }}
          >
            <option value="">All synced assets</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.container_name ? ` (${p.container_name})` : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Container
          <input
            className="eve-input w-40 ml-1"
            placeholder="Station warehouse name"
            value={containerName}
            onChange={(e) => setContainerName(e.target.value)}
          />
        </label>
        <label className="inline-flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={useMaxStock}
            onChange={(e) => setUseMaxStock(e.target.checked)}
          />
          Use max stock
        </label>
      </div>

      <SectionHead>Add planner row (ship hull to build)</SectionHead>
      <div className="flex flex-wrap gap-2 mb-3 items-end text-[11px]">
        <input
          className="eve-input w-36"
          placeholder="Fitting name"
          value={newFitName}
          onChange={(e) => setNewFitName(e.target.value)}
        />
        <input
          className="eve-input w-28"
          placeholder="Ship type ID"
          value={newFitTypeId}
          onChange={(e) => setNewFitTypeId(e.target.value)}
        />
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => void addFitting()}>
          Add row
        </button>
        <span className="text-[var(--text-muted)]">Uses SDE recipe for ship type — not module fit cost.</span>
      </div>

      <SectionHead>Build targets — click row to expand plan</SectionHead>
      <div className="border border-[var(--edge-dim)] mb-2 min-h-[280px] max-h-[min(52vh,520px)] overflow-auto eve-scroll">
        {sources.length ? (
          sources.map((src) => {
            const key = `${src.kind}:${src.id}`;
            const open = expandedKey === key;
            const bpRow = src.kind === "blueprint" ? blueprints.find((b) => b.id === src.id) : null;
            return (
              <div key={key} className="border-b border-[var(--edge-dim)]">
                <button
                  type="button"
                  className={`w-full flex gap-2 items-center py-1.5 px-2 hover:bg-[var(--row-hover)] text-left ${open ? "bg-[var(--panel-inset)]" : ""}`}
                  onClick={() => void runPlan(src)}
                  disabled={planLoading}
                >
                  {src.kind === "fitting" ? (
                    <img src={typeRenderUrl(src.typeId, 32)} alt="" width={24} height={24} />
                  ) : (
                    <img
                      src={blueprintScrollIconUrl(src.typeId, bpRow?.runs ?? -1, 32)}
                      alt=""
                      width={24}
                      height={24}
                    />
                  )}
                  <span className="flex-1 text-[11px]">
                    <strong>{src.label}</strong>
                    <span className="text-[var(--text-muted)] ml-1">({src.kind})</span>
                  </span>
                  <span className="text-[var(--text-muted)]">{open ? "▼" : "▶"}</span>
                </button>
                {open && plan && expandedKey === key ? (
                  <>
                    {src.kind === "fitting" ? <FittingShipRadar typeId={src.typeId} /> : null}
                    <ProductionPlanDetails
                      plan={plan}
                      loading={planLoading}
                      priceOverrides={priceOverrides}
                      stockAssignments={stockAssignments}
                      onPriceChange={(tid, v) => setPriceOverrides((p) => ({ ...p, [tid]: v }))}
                      onStockChange={(tid, v) => setStockAssignments((p) => ({ ...p, [tid]: v }))}
                      onRecalculate={() => void runPlan(src)}
                      onCopyBuyList={copyBuyList}
                    />
                  </>
                ) : null}
              </div>
            );
          })
        ) : (
          <p className="p-2 text-sm text-[var(--text-muted)]">Sync fittings/blueprints or add a ship row above.</p>
        )}
      </div>
      {planError ? <p className="text-[var(--danger)] text-sm">{planError}</p> : null}
    </div>
  );
}

function ProductionPlanDetails({
  plan,
  loading,
  priceOverrides,
  stockAssignments,
  onPriceChange,
  onStockChange,
  onRecalculate,
  onCopyBuyList,
}: {
  plan: ProductionPlan;
  loading: boolean;
  priceOverrides: Record<number, string>;
  stockAssignments: Record<number, string>;
  onPriceChange: (typeId: number, value: string) => void;
  onStockChange: (typeId: number, value: string) => void;
  onRecalculate: () => void;
  onCopyBuyList: () => void;
}) {
  const cf = plan.cash_flow;
  return (
    <div className="p-2 text-[10px] bg-[var(--surface-1)] border-t border-[var(--edge-dim)]">
      <div className="flex flex-wrap items-baseline gap-2 mb-2">
        <strong>Production Plan — {plan.plan_code}</strong>
        <span>{plan.source_name}</span>
        {plan.pricing_source ? (
          <span className="text-[var(--text-muted)]">
            Prices: {plan.pricing_source}
            {!plan.janice_configured ? " (Janice not configured — ESI fallback)" : ""}
          </span>
        ) : null}
        {plan.structure ? (
          <span className="text-[var(--text-muted)]">
            @ {plan.structure.structure_name} ({plan.structure.system_name}) ME bonus{" "}
            {plan.structure.material_bonus_pct}%
          </span>
        ) : null}
        <button type="button" className="eve-btn-sm ml-auto" onClick={onRecalculate} disabled={loading}>
          Recalculate
        </button>
        <button type="button" className="eve-btn-sm" onClick={onCopyBuyList}>
          Copy buy list
        </button>
        {plan.janice_buy_appraisal?.url ? (
          <a
            href={plan.janice_buy_appraisal.url}
            className="text-[var(--link)] text-[10px]"
            target="_blank"
            rel="noreferrer"
          >
            Janice buy list ({plan.janice_buy_appraisal.code})
          </a>
        ) : null}
      </div>

      {cf ? (
        <>
          <SectionHead>
            Cash-Flows ({plan.price_hub_label || "Jita"} sell/buy)
          </SectionHead>
          <table className="eve-table mb-2">
            <thead>
              <tr>
                <th />
                <th className="text-right">Buy Value</th>
                <th className="text-right">Sell Value</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Starting Stocks", cf.starting_stocks_buy, cf.starting_stocks_sell],
                ["End Stocks", cf.end_stocks_buy, cf.end_stocks_sell],
                ["Materials to Buy", cf.materials_to_buy_buy, cf.materials_to_buy_sell],
                ["Manufacturing Job Costs", cf.manufacturing_job_costs, null],
                ["Total Sales Taxes", cf.total_sales_taxes, null],
                ["Invention Cost", cf.invention_cost, null],
                ["End Products", cf.end_products_buy, cf.end_products_sell],
              ].map(([label, buy, sell]) => (
                <tr key={String(label)}>
                  <td>{label}</td>
                  <td className="num">{buy != null ? fmtIsk(buy) : ""}</td>
                  <td className="num">{sell != null ? fmtIsk(sell) : ""}</td>
                </tr>
              ))}
              <tr className="font-medium">
                <td>Expected Profit</td>
                <td className="num" colSpan={2}>
                  {fmtIsk(cf.expected_profit)} ISK
                </td>
              </tr>
            </tbody>
          </table>
        </>
      ) : null}

      {plan.job_time ? (
        <p className="text-[var(--text-muted)] mb-2">
          Job time: {plan.job_time.total_days} days total · end product{" "}
          {(plan.job_time.end_products_seconds / 86400).toFixed(2)} days
        </p>
      ) : null}

      <SectionHead>Stocks and Materials</SectionHead>
      <div className="overflow-auto max-h-[240px] mb-2">
        <table className="eve-table">
          <thead>
            <tr>
              <th>Name</th>
              <th className="text-right">Required</th>
              <th className="text-right">In stock</th>
              <th className="text-right">Use stock</th>
              <th className="text-right">To buy</th>
              <th className="text-right">Buy ISK</th>
              <th className="text-right">Price ISK</th>
              <th className="text-right">Vol m³</th>
            </tr>
          </thead>
          <tbody>
            {(plan.materials ?? []).map((m) => (
              <tr key={m.type_id}>
                <td>
                  <EveTypeIcon typeId={m.type_id} size={18} />
                  <span className="ml-1">{m.name}</span>
                  {m.is_component ? <span className="text-[var(--warn)] ml-1">comp</span> : null}
                </td>
                <td className="num">{m.required_qty.toLocaleString()}</td>
                <td className="num">{m.in_stock.toLocaleString()}</td>
                <td className="num">
                  <input
                    className="eve-input w-20 text-right"
                    value={stockAssignments[m.type_id] ?? String(m.start_amount)}
                    onChange={(e) => onStockChange(m.type_id, e.target.value)}
                  />
                </td>
                <td className="num">{m.to_buy.toLocaleString()}</td>
                <td className="num">{fmtIsk(m.to_buy_buy_value)}</td>
                <td className="num">
                  <input
                    className="eve-input w-24 text-right"
                    value={priceOverrides[m.type_id] ?? String(Math.round(m.buy_unit_price))}
                    onChange={(e) => onPriceChange(m.type_id, e.target.value)}
                  />
                </td>
                <td className="num">{m.volume_m3.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plan.end_products?.length ? (
        <>
          <SectionHead>End Products</SectionHead>
          <table className="eve-table mb-2">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-right">Qty</th>
                <th className="text-right">Vol</th>
                <th className="text-right">Sell/unit</th>
                <th className="text-right">Sell total</th>
              </tr>
            </thead>
            <tbody>
              {plan.end_products.map((p) => (
                <tr key={p.type_id}>
                  <td>{p.name}</td>
                  <td className="num">{p.amount}</td>
                  <td className="num">{p.volume_m3}</td>
                  <td className="num">{fmtIsk(p.sell_unit_price)}</td>
                  <td className="num">{fmtIsk(p.sell_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {plan.jobs?.length ? (
        <>
          <SectionHead>Jobs to Run</SectionHead>
          <table className="eve-table">
            <thead>
              <tr>
                <th>Blueprint</th>
                <th className="text-right">Runs</th>
                <th className="text-right">ME</th>
                <th className="text-right">Days</th>
                <th className="text-right">Job cost</th>
              </tr>
            </thead>
            <tbody>
              {plan.jobs.map((j, i) => (
                <tr key={`${j.name}-${i}`}>
                  <td>
                    {j.product_name ?? j.name}
                    {j.is_end_product ? " ★" : ""}
                  </td>
                  <td className="num">{j.runs}</td>
                  <td className="num">{j.me}</td>
                  <td className="num">{j.days}</td>
                  <td className="num">{fmtIsk(j.job_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </div>
  );
}
