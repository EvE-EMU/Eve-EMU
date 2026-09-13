"use client";

import { useMemo, useState } from "react";
import type { Invoice, MiningLog, OrgSettings, StructureTaxRule } from "@/lib/api";
import {
  canEditTaxForMoon,
  computeMoonProductivity,
  listStructures,
  parseStructure,
  taxScopeOptions,
} from "@/lib/moonProductivity";
import { MoonProductivityReport } from "./MoonProductivityReport";
import { MoonTimingPanel } from "@/components/tools/MoonTimingPanel";
import { DataField, EveWindow, RarityTag, SectionHead } from "./ui";
import { DesktopSurface } from "./WindowManager";

type TaxGranularity = "rarity" | "type";

function MoonTaxPanel({
  settings,
  taxRules,
  logs,
  invoices,
  windowId = "moon-tax",
  defaultX = 432,
  defaultY = 4,
  defaultWidth = 440,
  defaultHeight = 520,
  onApplyTax,
}: {
  settings: OrgSettings;
  taxRules: StructureTaxRule[];
  logs: MiningLog[];
  invoices: Invoice[];
  windowId?: string;
  defaultX?: number;
  defaultY?: number;
  defaultWidth?: number;
  defaultHeight?: number;
  onApplyTax?: (rates: { ruleId: number; r16: number; r32: number; r64: number }) => Promise<void>;
}) {
  const scopeOpts = useMemo(() => taxScopeOptions(logs), [logs]);
  const [taxScope, setTaxScope] = useState(scopeOpts[0]?.value ?? "scope:public");
  const [granularity, setGranularity] = useState<TaxGranularity>("rarity");

  const primaryRule = taxRules.find((r) => r.pattern === "*") || taxRules[0];
  const [rarityRates, setRarityRates] = useState({
    r4: 0,
    r8: 0,
    r16: Number(primaryRule?.r16_pct ?? 20),
    r32: Number(primaryRule?.r32_pct ?? 30),
    r64: Number(primaryRule?.r64_pct ?? 40),
  });

  const scopedLogs = useMemo(() => {
    if (taxScope.startsWith("moon:")) {
      return logs.filter((l) => l.structure_name === taxScope.slice(5));
    }
    if (taxScope === "scope:nationalised") {
      return logs.filter((l) => parseStructure(l.structure_name).moonType === "NATIONALISED");
    }
    return logs.filter((l) => parseStructure(l.structure_name).moonType === "PUBLIC");
  }, [logs, taxScope]);

  const oreTypes = useMemo(
    () => [...new Set(scopedLogs.map((l) => l.type_name))].sort(),
    [scopedLogs]
  );

  const [typeRates, setTypeRates] = useState<Record<string, number>>({});

  const effectiveTypeRates = useMemo(() => {
    const out: Record<string, number> = {};
    for (const ore of oreTypes) {
      out[ore] = typeRates[ore] ?? 20;
    }
    return out;
  }, [oreTypes, typeRates]);

  const scopeMeta = useMemo(() => {
    if (taxScope.startsWith("moon:")) {
      const name = taxScope.slice(5);
      return { label: name, ...parseStructure(name) };
    }
    return {
      label: taxScope === "scope:nationalised" ? "All nationalized moons" : "All public moons",
      moonType: taxScope === "scope:nationalised" ? "NATIONALISED" : "PUBLIC",
    } as const;
  }, [taxScope]);

  const canEdit = useMemo(() => {
    if (taxScope.startsWith("moon:")) {
      const name = taxScope.slice(5);
      return canEditTaxForMoon(name, parseStructure(name).moonType);
    }
    return true;
  }, [taxScope]);

  const revenue = useMemo(() => {
    if (granularity === "rarity") {
      const byR: Record<string, { volume: number; isk: number }> = {};
      for (const row of scopedLogs) {
        const r = row.moon_rarity.toLowerCase();
        if (!byR[r]) byR[r] = { volume: 0, isk: 0 };
        byR[r].volume += row.quantity;
        byR[r].isk += Number(row.isk_value);
      }
      return ["r4", "r8", "r16", "r32", "r64"]
        .filter((r) => byR[r])
        .map((r) => {
          const rate = rarityRates[r as keyof typeof rarityRates] ?? 0;
          const isk = byR[r].isk;
          return { key: r, label: r.toUpperCase(), volume: byR[r].volume, rate, collected: Math.round(isk * (rate / 100)) };
        });
    }

    const byType: Record<string, { volume: number; isk: number }> = {};
    for (const row of scopedLogs) {
      if (!byType[row.type_name]) byType[row.type_name] = { volume: 0, isk: 0 };
      byType[row.type_name].volume += row.quantity;
      byType[row.type_name].isk += Number(row.isk_value);
    }
    return Object.entries(byType).map(([type, v]) => {
      const rate = effectiveTypeRates[type] ?? 20;
      return {
        key: type,
        label: type,
        volume: v.volume,
        rate,
        collected: Math.round(v.isk * (rate / 100)),
      };
    });
  }, [scopedLogs, granularity, rarityRates, effectiveTypeRates]);

  const totalCollected = revenue.reduce((s, r) => s + r.collected, 0);

  const [savingTax, setSavingTax] = useState(false);

  const applyTax = async () => {
    if (!primaryRule || !onApplyTax) return;
    setSavingTax(true);
    try {
      await onApplyTax({
        ruleId: primaryRule.id,
        r16: rarityRates.r16,
        r32: rarityRates.r32,
        r64: rarityRates.r64,
      });
    } finally {
      setSavingTax(false);
    }
  };

  return (
    <EveWindow
      id={windowId}
      title="Moon tax management"
      defaultX={defaultX}
      defaultY={defaultY}
      defaultWidth={defaultWidth}
      defaultHeight={defaultHeight}
    >
      <div className="flex items-center gap-2 border-b border-[var(--edge-dim)] pb-1.5 mb-1">
        <div className="flex h-7 w-7 items-center justify-center border border-[var(--edge)] bg-[var(--panel-inset)] text-[9px] text-[var(--text-muted)]">
          CORP
        </div>
        <div>
          <p className="text-[11px] text-[var(--text)]">{settings.tax_corp_name}</p>
          <p className="text-[10px] text-[var(--text-muted)]">Corporation ID {settings.corporation_id}</p>
        </div>
      </div>

      <div className="mt-1 grid grid-cols-1 gap-1.5">
        <label className="block">
          <span className="eve-field-label block mb-0.5">Tax scope</span>
          <select
            className="eve-select w-full"
            value={taxScope}
            onChange={(e) => setTaxScope(e.target.value)}
          >
            {["Scope", "Individual moons", "Your moons"].map((group) => {
              const items = scopeOpts.filter((o) => o.group === group);
              if (!items.length) return null;
              return (
                <optgroup key={group} label={group}>
                  {items.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </optgroup>
              );
            })}
          </select>
        </label>
        <label className="block">
          <span className="eve-field-label block mb-0.5">Rate granularity</span>
          <select
            className="eve-select w-full"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as TaxGranularity)}
            disabled={!canEdit}
          >
            <option value="rarity">By moon goo tier (R4, R8, R16…)</option>
            <option value="type">By individual ore type (Coesite, Bitumens…)</option>
          </select>
        </label>
      </div>

      {!canEdit ? (
        <p className="eve-admin-note mt-1">Private moons you do not rent — tax locked to renter.</p>
      ) : null}

      <DataField label="Applying to" value={scopeMeta.label} />

      <div className="mt-1">
        <SectionHead>Tax adjustment</SectionHead>
        {granularity === "rarity"
          ? (["r4", "r8", "r16", "r32", "r64"] as const).map((r) => (
              <div key={r} className="eve-slider-row">
                <span className="eve-slider-tier">{r.toUpperCase()}</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  disabled={!canEdit}
                  value={rarityRates[r]}
                  onChange={(e) =>
                    setRarityRates((prev) => ({ ...prev, [r]: Number(e.target.value) }))
                  }
                />
                <span className="eve-slider-pct">{rarityRates[r]}%</span>
              </div>
            ))
          : oreTypes.map((ore) => (
              <div key={ore} className="eve-slider-row">
                <span className="eve-slider-tier eve-slider-tier--wide" title={ore}>
                  {ore}
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  disabled={!canEdit}
                  value={effectiveTypeRates[ore]}
                  onChange={(e) =>
                    setTypeRates((prev) => ({ ...prev, [ore]: Number(e.target.value) }))
                  }
                />
                <span className="eve-slider-pct">{effectiveTypeRates[ore]}%</span>
              </div>
            ))}
      </div>

      <div className="mt-1">
        <SectionHead>Revenue breakdown</SectionHead>
        <table className="eve-table">
          <thead>
            <tr>
              <th>{granularity === "rarity" ? "Tier" : "Ore type"}</th>
              <th className="text-right">Volume</th>
              <th className="text-right">Rate</th>
              <th className="text-right">Collected</th>
            </tr>
          </thead>
          <tbody>
            {revenue.map((row) => (
              <tr key={row.key}>
                <td>
                  {granularity === "rarity" ? <RarityTag rarity={row.key} /> : row.label}
                </td>
                <td className="num">{row.volume.toLocaleString()}</td>
                <td className="num">{row.rate}%</td>
                <td className="num text-[var(--text)]">{row.collected.toLocaleString()}</td>
              </tr>
            ))}
            <tr>
              <td colSpan={3} className="text-[var(--text-muted)]">
                Total
              </td>
              <td className="num text-[var(--text)]">{totalCollected.toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-1">
        <SectionHead>Recent bills</SectionHead>
        <table className="eve-table">
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Pilot</th>
              <th className="text-right">Due</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {invoices.slice(0, 5).map((inv) => (
              <tr key={inv.id}>
                <td className="font-mono text-[10px] text-[var(--text-dim)]">{inv.invoice_number}</td>
                <td>{inv.character_name}</td>
                <td className="num">{Number(inv.total_due_isk).toLocaleString()}</td>
                <td
                  className={
                    inv.status === "paid"
                      ? "text-[var(--ok)]"
                      : inv.on_naughty_list
                        ? "text-[var(--danger)]"
                        : "text-[var(--warn)]"
                  }
                >
                  {inv.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2 flex gap-1">
        <button
          type="button"
          className="eve-btn eve-btn-primary"
          disabled={!canEdit || savingTax}
          onClick={() => void applyTax()}
        >
          {savingTax ? "Applying…" : "Apply tax"}
        </button>
        <button
          type="button"
          className="eve-btn"
          disabled={!canEdit}
          onClick={() =>
            setRarityRates({
              r4: 0,
              r8: 0,
              r16: Number(primaryRule?.r16_pct ?? 20),
              r32: Number(primaryRule?.r32_pct ?? 30),
              r64: Number(primaryRule?.r64_pct ?? 40),
            })
          }
        >
          Reset
        </button>
      </div>
    </EveWindow>
  );
}

function ProductivityWindow({
  id,
  title,
  structure,
  logs,
  invoices,
  defaultX,
  defaultY,
}: {
  id: string;
  title: string;
  structure: string;
  logs: MiningLog[];
  invoices: Invoice[];
  defaultX: number;
  defaultY: number;
}) {
  const stats = useMemo(
    () => computeMoonProductivity(structure, logs, invoices),
    [structure, logs, invoices]
  );

  return (
    <EveWindow
      id={id}
      title={title}
      defaultX={defaultX}
      defaultY={defaultY}
      defaultWidth={460}
      defaultHeight={500}
    >
      <MoonProductivityReport stats={stats} />
    </EveWindow>
  );
}

export { MoonTaxPanel };

export function MoonOperations({
  logs,
  invoices,
  settings,
  taxRules,
  embedded,
}: {
  logs: MiningLog[];
  invoices: Invoice[];
  settings: OrgSettings;
  taxRules: StructureTaxRule[];
  embedded?: boolean;
}) {
  const structures = useMemo(() => listStructures(logs), [logs]);
  const primaryStructure = structures[0] || "DS-LO3 - PUBLIC P9M1";
  const nationalized = structures.find((s) => parseStructure(s).moonType === "NATIONALISED") || primaryStructure;
  const reportMoon = structures[1] || primaryStructure;

  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <ProductivityWindow
        id="moon-productivity"
        title="Moon Productivity Report"
        structure={reportMoon}
        logs={logs}
        invoices={invoices}
        defaultX={4}
        defaultY={492}
      />
      <ProductivityWindow
        id="nationalized-inspector"
        title="Nationalized Moon Inspector"
        structure={nationalized}
        logs={logs}
        invoices={invoices}
        defaultX={472}
        defaultY={492}
      />
      <MiningLedger logs={logs} />
      <EveWindow
        id="moon-timing"
        title="Moon Mining Timing"
        defaultX={40}
        defaultY={40}
        defaultWidth={860}
        defaultHeight={520}
      >
        <MoonTimingPanel />
      </EveWindow>
    </DesktopSurface>
  );
}

export function MiningLedger({ logs }: { logs: MiningLog[] }) {
  const preview = logs.slice(0, 8);

  return (
    <EveWindow
      id="observer-log"
      title={`Observer Log — ${logs.length}`}
      defaultX={880}
      defaultY={4}
      defaultWidth={360}
      defaultHeight={220}
    >
      <div>
        <table className="eve-table min-w-[320px]">
          <thead>
            <tr>
              <th>Date</th>
              <th>Structure</th>
              <th>Pilot</th>
              <th>Ore</th>
              <th>Tier</th>
              <th className="text-right">Qty</th>
            </tr>
          </thead>
          <tbody>
            {preview.map((row) => (
              <tr key={row.id}>
                <td className="text-[var(--text-dim)]">{row.mined_date}</td>
                <td>{row.structure_name}</td>
                <td>{row.character_name}</td>
                <td>{row.type_name}</td>
                <td>
                  <RarityTag rarity={row.moon_rarity} />
                </td>
                <td className="num">{row.quantity.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}
