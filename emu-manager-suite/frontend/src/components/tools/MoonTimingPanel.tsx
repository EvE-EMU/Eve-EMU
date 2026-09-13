"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { SectionHead, StatusStrip } from "@/components/ui";

type MoonRow = {
  structure_name: string;
  last_mined_date: string;
  days_since_last: number;
  phase: string;
  phase_label: string;
  estimated_window_end: string;
  peak_day: string;
  peak_isk: number;
  isk_7d: number;
  isk_30d: number;
  qty_7d: number;
  unique_miners: number;
  rarities: string[];
  ore_types: string[];
  median_gap_days: number | null;
  next_pop_estimate: string | null;
  recent_days: { date: string; quantity: number; isk_value: number; miners: number }[];
};

function fmtIsk(n: number) {
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function phaseClass(phase: string) {
  if (phase === "mining_window") return "text-[var(--ok)]";
  if (phase === "recent") return "text-[var(--warn)]";
  return "text-[var(--text-muted)]";
}

export function MoonTimingPanel() {
  const [rows, setRows] = useState<MoonRow[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [days, setDays] = useState(45);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/tools/moon-timing?days=${days}&idle_days=7`, { cache: "no-store" });
      if (!res.ok) {
        setError("Failed to load moon timing.");
        return;
      }
      const data = await res.json();
      setRows(data.structures || []);
      setSummary(data.summary || {});
    } catch {
      setError("Failed to load moon timing.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full">
      <StatusStrip>
        Moon mining timing from live mining logs · active window {summary.mining_window ?? 0} · recent{" "}
        {summary.recent ?? 0} · idle {summary.idle ?? 0} · 7d ISK {fmtIsk(summary.isk_7d || 0)}
      </StatusStrip>
      <div className="flex flex-wrap gap-2 items-end text-[11px]">
        <label>
          Lookback days
          <input
            className="eve-input w-16 ml-1"
            type="number"
            min={7}
            max={180}
            value={days}
            onChange={(e) => setDays(Math.max(7, parseInt(e.target.value, 10) || 45))}
          />
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {error ? <p className="text-[var(--danger)] text-sm">{error}</p> : null}
      <p className="text-[10px] text-[var(--text-muted)]">
        Phases use mining activity: active = mined in last 2 days (typical post-pop window), idle = no mining for 7+
        days. Next pop estimate uses median gaps between active days when available.
      </p>
      <div className="overflow-auto min-h-0 flex-1 border border-[var(--edge-dim)]">
        <table className="eve-table text-[11px]">
          <thead>
            <tr>
              <th>Structure / moon</th>
              <th>Phase</th>
              <th>Last mined</th>
              <th className="text-end">Days idle</th>
              <th className="text-end">7d ISK</th>
              <th className="text-end">30d ISK</th>
              <th>Next est.</th>
              <th>Rarity</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r.structure_name}>
                <tr
                  className="cursor-pointer"
                  onClick={() => setExpanded(expanded === r.structure_name ? null : r.structure_name)}
                >
                  <td>
                    <strong>{r.structure_name}</strong>
                    <div className="text-[9px] text-[var(--text-muted)]">
                      {r.unique_miners} miners · peak {r.peak_day}
                    </div>
                  </td>
                  <td className={phaseClass(r.phase)}>{r.phase_label}</td>
                  <td>{r.last_mined_date}</td>
                  <td className="text-end">{r.days_since_last}</td>
                  <td className="text-end">{fmtIsk(r.isk_7d)}</td>
                  <td className="text-end">{fmtIsk(r.isk_30d)}</td>
                  <td className="text-[10px]">{r.next_pop_estimate || "—"}</td>
                  <td className="text-[10px]">{r.rarities.join(", ") || "—"}</td>
                </tr>
                {expanded === r.structure_name ? (
                  <tr>
                    <td colSpan={8} className="bg-[var(--panel-inset)] text-[10px]">
                      <SectionHead>Recent activity</SectionHead>
                      <div className="mb-1 text-[var(--text-muted)]">
                        Ores: {r.ore_types.join(", ") || "—"} · Window end est: {r.estimated_window_end}
                        {r.median_gap_days != null ? ` · Median gap ${r.median_gap_days}d` : ""}
                      </div>
                      <table className="eve-table eve-table-compact w-full">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th className="text-end">Qty</th>
                            <th className="text-end">ISK</th>
                            <th className="text-end">Miners</th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.recent_days.map((d) => (
                            <tr key={d.date}>
                              <td>{d.date}</td>
                              <td className="text-end">{d.quantity.toLocaleString()}</td>
                              <td className="text-end">{fmtIsk(d.isk_value)}</td>
                              <td className="text-end">{d.miners}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
        {!rows.length && !loading ? (
          <p className="p-3 text-sm text-[var(--text-muted)]">
            No mining logs in the lookback window — import observer / tax mining data to populate timing.
          </p>
        ) : null}
      </div>
    </div>
  );
}
