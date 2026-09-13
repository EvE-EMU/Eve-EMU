"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useAuth } from "@/components/AuthProvider";
import { KpiStrip, KpiTile, SectionHead } from "@/components/ui";
import { CharSheetSortButton } from "@/components/tools/CharSheetTableToolbar";
import { sortByKey, useTableSort } from "@/lib/useTableSort";

export type PiColonyRow = {
  character_id: number;
  character_name: string;
  planet_id: number;
  solar_system_id: number;
  system_name: string;
  planet_type: string;
  upgrade_level: number;
  num_pins: number;
  active_extractors: number;
  expired_extractors: number;
  storage_used: number;
  storage_capacity_est: number;
  storage_fill_pct: number;
  next_expiry_at: string | null;
  hours_to_expiry: number | null;
  status: "ok" | "idle" | "attention" | string;
  attention_reasons: string[];
  pins: {
    pin_id: number;
    type_name: string;
    category: string;
    contents_label: string;
    content_total: number;
    expiry_time: string | null;
    last_cycle_start: string | null;
  }[];
};

type PiOverview = {
  character_count: number;
  colony_count: number;
  attention_count: number;
  pi_scope_character_count?: number;
  scope_errors?: Record<string, string>;
  scope_error_details?: { character_id: number; character_name: string; message: string }[];
  colonies: PiColonyRow[];
  scope_note?: string;
};

function fmtWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtCountdown(hours: number | null) {
  if (hours == null) return "—";
  if (hours <= 0) return "Expired";
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export function PiOverviewPanel() {
  const { session } = useAuth();
  const [overview, setOverview] = useState<PiOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlanet, setSelectedPlanet] = useState<number | null>(null);
  const [filter, setFilter] = useState<"all" | "attention" | "idle">("all");
  type PiSort = "pilot" | "planet" | "extractors" | "storage" | "expiry" | "status";
  const { sortKey, sortAsc, toggleSort } = useTableSort<PiSort>("expiry", true);

  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/audit/roster/pi", { cache: "no-store", credentials: "same-origin" });
      if (!res.ok) {
        setOverview(null);
        setError("Unable to load PI overview. Sync characters after granting PI scope.");
        return;
      }
      setOverview((await res.json()) as PiOverview);
    } catch {
      setError("Unable to load PI overview.");
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const syncNow = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      const res = await fetch("/api/audit/roster/pi/sync", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setError("PI sync failed — check SSO scope and try again.");
        return;
      }
      setOverview((await res.json()) as PiOverview);
    } catch {
      setError("PI sync failed.");
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    if (session.authenticated) void load();
  }, [session.authenticated, load]);

  const rows = useMemo(() => {
    if (!overview) return [];
    let list = overview.colonies;
    if (filter === "attention") list = list.filter((c) => c.status === "attention");
    if (filter === "idle") list = list.filter((c) => c.status === "idle");
    return sortByKey(list, sortKey, sortAsc, (row, key) => {
      if (key === "pilot") return row.character_name;
      if (key === "planet") return row.system_name;
      if (key === "extractors") return row.active_extractors;
      if (key === "storage") return row.storage_fill_pct;
      if (key === "expiry") return row.hours_to_expiry ?? 99999;
      return row.status;
    });
  }, [overview, filter, sortKey, sortAsc]);

  const selected = useMemo(
    () => rows.find((r) => r.planet_id === selectedPlanet) ?? overview?.colonies.find((r) => r.planet_id === selectedPlanet),
    [rows, overview?.colonies, selectedPlanet]
  );

  if (!session.authenticated) {
    return <p className="text-[11px] text-[var(--text-muted)] p-3">Log in to view planetary interaction colonies.</p>;
  }

  if (loading && !overview) {
    return <p className="text-[11px] text-[var(--text-muted)] p-3">Loading PI colonies…</p>;
  }

  return (
    <div className="text-[11px] space-y-2 p-1">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1">
          <h2 className="text-[13px] font-medium">Planetary interaction</h2>
          <p className="text-[10px] text-[var(--text-muted)] mt-1">
            {overview?.scope_note ??
              "Colony layout, storage, and extractor timers across all linked characters."}
          </p>
        </div>
        <button type="button" className="eve-btn-sm" disabled={syncing} onClick={() => void syncNow()}>
          {syncing ? "Syncing…" : "Sync PI"}
        </button>
        <button type="button" className="eve-btn-sm" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {error ? <p className="text-[var(--danger)]">{error}</p> : null}

      {overview?.scope_error_details?.length ? (
        <div className="border border-[var(--warn)] text-[var(--warn)] p-2 text-[10px] space-y-1">
          <strong>PI sync issues</strong>
          {overview.scope_error_details.map((row) => (
            <div key={row.character_id}>
              {row.character_name}: {row.message}
            </div>
          ))}
        </div>
      ) : overview?.scope_errors && Object.keys(overview.scope_errors).length ? (
        <div className="border border-[var(--warn)] text-[var(--warn)] p-2 text-[10px] space-y-1">
          <strong>PI sync issues</strong>
          {Object.entries(overview.scope_errors).map(([cid, msg]) => (
            <div key={cid}>
              Character {cid}: {msg}
            </div>
          ))}
        </div>
      ) : null}

      {overview ? (
        <>
          <KpiStrip>
            <KpiTile label="Colonies" value={String(overview.colony_count)} tone="accent" />
            <KpiTile label="Needs attention" value={String(overview.attention_count)} tone={overview.attention_count ? "warn" : "ok"} />
            <KpiTile label="Characters" value={String(overview.character_count)} />
          </KpiStrip>

          <div className="flex gap-1 mt-2">
            {(["all", "attention", "idle"] as const).map((f) => (
              <button
                key={f}
                type="button"
                className={clsx("eve-btn-sm", filter === f && "eve-btn-primary")}
                onClick={() => setFilter(f)}
              >
                {f === "all" ? "All planets" : f === "attention" ? "Attention" : "Idle"}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3 mt-2">
            <div className="overflow-x-auto eve-scroll">
              <table className="eve-table min-w-full">
                <thead>
                  <tr>
                    <th><CharSheetSortButton label="Pilot" active={sortKey === "pilot"} asc={sortAsc} onClick={() => toggleSort("pilot")} /></th>
                    <th><CharSheetSortButton label="Planet" active={sortKey === "planet"} asc={sortAsc} onClick={() => toggleSort("planet")} /></th>
                    <th><CharSheetSortButton label="Extractors" active={sortKey === "extractors"} asc={sortAsc} onClick={() => toggleSort("extractors")} /></th>
                    <th><CharSheetSortButton label="Storage" active={sortKey === "storage"} asc={sortAsc} onClick={() => toggleSort("storage")} /></th>
                    <th><CharSheetSortButton label="Head expires" active={sortKey === "expiry"} asc={sortAsc} onClick={() => toggleSort("expiry")} /></th>
                    <th><CharSheetSortButton label="Status" active={sortKey === "status"} asc={sortAsc} onClick={() => toggleSort("status")} /></th>
                  </tr>
                </thead>
                <tbody>
                {rows.map((row) => (
                  <tr
                    key={`${row.character_id}-${row.planet_id}`}
                    className={clsx("cursor-pointer", selectedPlanet === row.planet_id && "bg-[var(--surface-raised)]")}
                    onClick={() => setSelectedPlanet(row.planet_id)}
                  >
                    <td className="truncate max-w-[90px]" title={row.character_name}>
                      {row.character_name}
                    </td>
                    <td>
                      <div>{row.system_name}</div>
                      <div className="text-[9px] text-[var(--text-dim)] capitalize">
                        {row.planet_type} · CC L{row.upgrade_level}
                      </div>
                    </td>
                    <td className="font-mono">
                      {row.active_extractors} active
                      {row.expired_extractors ? ` / ${row.expired_extractors} expired` : ""}
                    </td>
                    <td>
                      {row.storage_fill_pct.toFixed(0)}%
                      <span className="text-[9px] text-[var(--text-muted)] block">
                        {row.storage_used.toLocaleString()} units
                      </span>
                    </td>
                    <td className="text-[10px]">
                      {fmtCountdown(row.hours_to_expiry)}
                      {row.next_expiry_at ? (
                        <span className="text-[9px] text-[var(--text-dim)] block">{fmtWhen(row.next_expiry_at)}</span>
                      ) : null}
                    </td>
                    <td>
                      <span
                        className={clsx(
                          "capitalize text-[10px]",
                          row.status === "attention" && "text-[var(--warn)]",
                          row.status === "idle" && "text-[var(--danger)]",
                          row.status === "ok" && "text-[var(--ok)]"
                        )}
                      >
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
                </tbody>
              </table>
              {!rows.length ? (
                <p className="text-[10px] text-[var(--text-muted)] p-2">
                  {overview.pi_scope_character_count ? (
                    <>
                      No PI colonies in snapshot yet. Click <strong>Sync PI</strong> to pull colony data from ESI
                      (scope is granted for {overview.pi_scope_character_count} character
                      {overview.pi_scope_character_count === 1 ? "" : "s"}).
                    </>
                  ) : (
                    <>
                      No PI scope on linked characters. Grant{" "}
                      <code className="text-[9px]">esi-planets.manage_planets.v1</code>, re-authorize SSO, then click{" "}
                      <strong>Sync PI</strong>.
                    </>
                  )}
                </p>
              ) : null}
            </div>

            <div className="border border-[var(--border)] p-2 min-h-[120px]">
              <SectionHead>Colony detail</SectionHead>
              {!selected ? (
                <p className="text-[10px] text-[var(--text-muted)]">Select a planet for pin storage and timers.</p>
              ) : (
                <div className="space-y-2 text-[10px]">
                  <p>
                    <strong>{selected.system_name}</strong> — {selected.character_name}
                  </p>
                  {selected.attention_reasons.length ? (
                    <ul className="text-[var(--warn)] space-y-1">
                      {selected.attention_reasons.map((r) => (
                        <li key={r}>• {r}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[var(--ok)]">Colony running normally.</p>
                  )}
                  <SectionHead>Pins</SectionHead>
                  <table className="eve-table text-[9px] w-full">
                    <thead>
                      <tr>
                        <th>Pin</th>
                        <th>Storage</th>
                        <th>Timer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.pins.map((pin) => (
                        <tr key={pin.pin_id}>
                          <td>
                            <div>{pin.type_name}</div>
                            <div className="text-[var(--text-dim)] capitalize">{pin.category}</div>
                          </td>
                          <td className="truncate max-w-[100px]" title={pin.contents_label}>
                            {pin.contents_label}
                          </td>
                          <td className="text-[9px]">
                            {pin.expiry_time ? fmtWhen(pin.expiry_time) : pin.last_cycle_start ? "Cycle active" : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
