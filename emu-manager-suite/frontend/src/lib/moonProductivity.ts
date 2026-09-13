import type { Invoice, MiningLog } from "@/lib/api";

export type MoonMeta = {
  system: string;
  moonType: "PUBLIC" | "PRIVATE" | "NATIONALISED" | "UNKNOWN";
  rarity: string;
  ref: string;
  region: string;
};

export function parseStructure(name: string): MoonMeta {
  const parts = name.split(" - ");
  const system = parts[0]?.trim() || name;
  const rest = parts[1]?.trim() || "";
  const moonType =
    (rest.match(/(PUBLIC|PRIVATE|NATIONALISED)/i)?.[1]?.toUpperCase() as MoonMeta["moonType"]) ||
    "UNKNOWN";
  const rarity = rest.match(/(R4|R8|R16|R32|R64)/i)?.[1]?.toLowerCase() || "mixed";
  const ref = rest.replace(/(PUBLIC|PRIVATE|NATIONALISED|R\d+)/gi, "").trim() || system;
  return { system, moonType, rarity, ref, region: "Delve" };
}

/** Private moons the viewer may edit tax for (populated from rental leases when wired). */
export const RENTER_MOONS = new Set<string>();

export function canEditTaxForMoon(structure: string, moonType: MoonMeta["moonType"]) {
  if (moonType === "PRIVATE") return RENTER_MOONS.has(structure);
  return moonType === "NATIONALISED" || moonType === "PUBLIC";
}

export type MoonProductivity = {
  structure: string;
  meta: MoonMeta;
  totalM3: number;
  totalIsk: number;
  pullCount: number;
  dayCount: number;
  avgIskMined: number;
  avgIskPerPull: number;
  avgM3Mined: number;
  avgM3PerPull: number;
  avgPullsPerDay: number;
  typicalMineTimeHours: number;
  lastJackpot: { date: string; isk: number; pilot: string; m3: number };
  lastExtraction: { date: string; time: string };
  nextExtraction: { date: string; time: string };
  topCorps: { name: string; m3: number; isk: number; pulls: number }[];
  topMiners: { name: string; corp: string; m3: number; isk: number; pulls: number }[];
  taxIncome: number;
  oreTypes: string[];
};

export function computeMoonProductivity(
  structure: string,
  logs: MiningLog[],
  invoices: Invoice[],
  taxRatePct = 25
): MoonProductivity {
  const rows = logs.filter((l) => l.structure_name === structure);
  const meta = parseStructure(structure);

  const byDate = new Map<string, typeof rows>();
  for (const row of rows) {
    const list = byDate.get(row.mined_date) ?? [];
    list.push(row);
    byDate.set(row.mined_date, list);
  }

  const totalM3 = rows.reduce((s, r) => s + r.quantity, 0);
  const totalIsk = rows.reduce((s, r) => s + Number(r.isk_value), 0);
  const pullCount = rows.length;
  const dayCount = Math.max(1, byDate.size);

  let bestJackpot = { date: "—", isk: 0, pilot: "—", m3: 0 };
  for (const [date, dayRows] of byDate) {
    const dayIsk = dayRows.reduce((s, r) => s + Number(r.isk_value), 0);
    const dayM3 = dayRows.reduce((s, r) => s + r.quantity, 0);
    const top = dayRows.reduce((a, b) => (Number(b.isk_value) > Number(a.isk_value) ? b : a), dayRows[0]);
    if (dayIsk > bestJackpot.isk) {
      bestJackpot = { date, isk: dayIsk, pilot: top?.character_name ?? "—", m3: dayM3 };
    }
  }

  const dates = [...byDate.keys()].sort();
  const lastDate = dates[dates.length - 1] ?? new Date().toISOString().slice(0, 10);
  const nextDate = addDays(lastDate, 3);

  const corpMap = new Map<string, { m3: number; isk: number; pulls: number }>();
  const minerMap = new Map<string, { corp: string; m3: number; isk: number; pulls: number }>();

  for (const row of rows) {
    const corp = "Unknown Corp";
    const c = corpMap.get(corp) ?? { m3: 0, isk: 0, pulls: 0 };
    c.m3 += row.quantity;
    c.isk += Number(row.isk_value);
    c.pulls += 1;
    corpMap.set(corp, c);

    const m = minerMap.get(row.character_name) ?? { corp, m3: 0, isk: 0, pulls: 0 };
    m.m3 += row.quantity;
    m.isk += Number(row.isk_value);
    m.pulls += 1;
    minerMap.set(row.character_name, m);
  }

  const structureInvoices = invoices.filter((i) => i.structure_name === structure);
  const taxIncome =
    structureInvoices.reduce((s, i) => s + Number(i.amount_paid_isk), 0) ||
    Math.round(totalIsk * (taxRatePct / 100) * 0.35);

  return {
    structure,
    meta,
    totalM3,
    totalIsk,
    pullCount,
    dayCount,
    avgIskMined: Math.round(totalIsk / dayCount),
    avgIskPerPull: pullCount ? Math.round(totalIsk / pullCount) : 0,
    avgM3Mined: Math.round(totalM3 / dayCount),
    avgM3PerPull: pullCount ? Math.round(totalM3 / pullCount) : 0,
    avgPullsPerDay: Math.round((pullCount / dayCount) * 10) / 10,
    typicalMineTimeHours: Math.round((totalM3 / Math.max(pullCount, 1)) / 1200),
    lastJackpot: bestJackpot,
    lastExtraction: { date: lastDate, time: "14:32 EVE" },
    nextExtraction: { date: nextDate, time: "14:32 EVE" },
    topCorps: [...corpMap.entries()]
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.isk - a.isk)
      .slice(0, 5),
    topMiners: [...minerMap.entries()]
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.isk - a.isk)
      .slice(0, 5),
    taxIncome,
    oreTypes: [...new Set(rows.map((r) => r.type_name))],
  };
}

function addDays(iso: string, days: number) {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function listStructures(logs: MiningLog[]) {
  return [...new Set(logs.map((l) => l.structure_name))];
}

export function taxScopeOptions(logs: MiningLog[]) {
  const structures = listStructures(logs);
  const opts: { value: string; label: string; group: string }[] = [
    { value: "scope:nationalised", label: "All nationalized moons", group: "Scope" },
    { value: "scope:public", label: "All public moons", group: "Scope" },
  ];
  for (const s of structures) {
    const meta = parseStructure(s);
    if (meta.moonType === "PRIVATE" && RENTER_MOONS.has(s)) {
      opts.push({ value: `moon:${s}`, label: `${s} (your rental)`, group: "Your moons" });
    } else if (meta.moonType !== "PRIVATE") {
      opts.push({ value: `moon:${s}`, label: s, group: "Individual moons" });
    }
  }
  return opts;
}
