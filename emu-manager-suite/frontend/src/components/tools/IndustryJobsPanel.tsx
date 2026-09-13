"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { KpiStrip, KpiTile, StatusStrip } from "@/components/ui";
import type { IndyJobRecord } from "@/lib/api";
import { formatEveTime } from "@/lib/eveTime";

type SortKey =
  | "character"
  | "pilot"
  | "blueprint"
  | "product"
  | "activity"
  | "location"
  | "runs"
  | "status"
  | "completes"
  | "time_left";

function timeLeftMs(endsAt: string | null | undefined, nowMs: number): number | null {
  if (!endsAt) return null;
  const end = Date.parse(endsAt);
  if (Number.isNaN(end)) return null;
  return end - nowMs;
}

function formatTimeLeft(endsAt: string | null | undefined, status: string, nowMs: number): string {
  const statusLower = (status || "").toLowerCase();
  if (statusLower === "delivered" || statusLower === "cancelled") return "—";
  const ms = timeLeftMs(endsAt, nowMs);
  if (ms == null) return "—";
  if (ms <= 0) {
    return statusLower === "active" || statusLower === "paused" ? "Ready" : "Done";
  }
  const hours = ms / 3_600_000;
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m`;
  if (hours < 48) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

function sortJobs(rows: IndyJobRecord[], key: SortKey, asc: boolean, nowMs: number): IndyJobRecord[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "character") return a.character_name.localeCompare(b.character_name) * dir;
    if (key === "pilot") {
      return (a.installer_name || a.character_name).localeCompare(b.installer_name || b.character_name) * dir;
    }
    if (key === "blueprint") return a.blueprint_name.localeCompare(b.blueprint_name) * dir;
    if (key === "product") return (a.output_type_name || "").localeCompare(b.output_type_name || "") * dir;
    if (key === "activity") return a.activity.localeCompare(b.activity) * dir;
    if (key === "location") return a.location_name.localeCompare(b.location_name) * dir;
    if (key === "runs") return (a.runs - b.runs) * dir;
    if (key === "status") return a.status.localeCompare(b.status) * dir;
    if (key === "completes") {
      const ta = Date.parse(a.ends_at || "") || 0;
      const tb = Date.parse(b.ends_at || "") || 0;
      return (ta - tb) * dir;
    }
    const la = timeLeftMs(a.ends_at, nowMs) ?? Number.MAX_SAFE_INTEGER;
    const lb = timeLeftMs(b.ends_at, nowMs) ?? Number.MAX_SAFE_INTEGER;
    return (la - lb) * dir;
  });
}

export function IndustryJobsPanel({
  jobs,
  onSync,
  syncing,
  syncError,
  onRefresh,
}: {
  jobs: IndyJobRecord[];
  onSync: () => void;
  syncing: boolean;
  syncError: string | null;
  onRefresh: () => void;
}) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("time_left");
  const [sortAsc, setSortAsc] = useState(true);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const statuses = useMemo(() => {
    const set = new Set(jobs.map((j) => j.status).filter(Boolean));
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [jobs]);

  const activeCount = jobs.filter((j) => {
    const s = (j.status || "").toLowerCase();
    return s === "active" || s === "paused";
  }).length;

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = jobs.filter((j) => {
      if (statusFilter && j.status !== statusFilter) return false;
      if (!q) return true;
      const hay = [
        j.character_name,
        j.installer_name,
        j.blueprint_name,
        j.output_type_name,
        j.activity,
        j.location_name,
        j.status,
        j.runs,
        j.job_id,
        formatEveTime(j.ends_at),
        formatTimeLeft(j.ends_at, j.status, nowMs),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortJobs(filtered, sortKey, sortAsc, nowMs);
  }, [jobs, query, statusFilter, sortKey, sortAsc, nowMs]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(key === "character" || key === "pilot" || key === "blueprint" || key === "location");
    }
  };

  return (
    <div className="flex flex-col min-h-0 h-full text-[11px]">
      <StatusStrip>
        Manufacturing, research, invention, and copy jobs from ESI — sync linked characters with industry scope
      </StatusStrip>
      <div className="flex flex-wrap gap-2 items-center mb-2">
        <button type="button" className="eve-btn-sm" onClick={onSync} disabled={syncing}>
          {syncing ? "Syncing…" : "Sync from ESI"}
        </button>
        <button type="button" className="eve-btn-sm" onClick={onRefresh}>
          Refresh
        </button>
        {syncError ? <span className="text-[var(--danger)] text-[10px]">{syncError}</span> : null}
      </div>
      <KpiStrip>
        <KpiTile label="Active / paused" value={String(activeCount)} tone="accent" />
        <KpiTile label="Total jobs" value={String(jobs.length)} />
      </KpiStrip>
      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Filter jobs…"
        shown={rows.length}
        total={jobs.length}
        filters={
          <select
            className="eve-select text-[10px]"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        }
      />
      <div className="flex-1 min-h-0 overflow-auto eve-scroll mt-1">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th>
                <CharSheetSortButton
                  label="Character"
                  active={sortKey === "character"}
                  asc={sortAsc}
                  onClick={() => toggleSort("character")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Pilot"
                  active={sortKey === "pilot"}
                  asc={sortAsc}
                  onClick={() => toggleSort("pilot")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Blueprint"
                  active={sortKey === "blueprint"}
                  asc={sortAsc}
                  onClick={() => toggleSort("blueprint")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Product"
                  active={sortKey === "product"}
                  asc={sortAsc}
                  onClick={() => toggleSort("product")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Activity"
                  active={sortKey === "activity"}
                  asc={sortAsc}
                  onClick={() => toggleSort("activity")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Location"
                  active={sortKey === "location"}
                  asc={sortAsc}
                  onClick={() => toggleSort("location")}
                />
              </th>
              <th className="text-right">
                <CharSheetSortButton
                  label="Runs"
                  active={sortKey === "runs"}
                  asc={sortAsc}
                  align="right"
                  onClick={() => toggleSort("runs")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Status"
                  active={sortKey === "status"}
                  asc={sortAsc}
                  onClick={() => toggleSort("status")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Completes"
                  active={sortKey === "completes"}
                  asc={sortAsc}
                  onClick={() => toggleSort("completes")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Time left"
                  active={sortKey === "time_left"}
                  asc={sortAsc}
                  onClick={() => toggleSort("time_left")}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((j) => {
                const pilot = j.installer_name || j.character_name;
                const samePilot = pilot === j.character_name;
                return (
                  <tr key={j.id}>
                    <td className="truncate max-w-[90px]" title={j.character_name}>
                      {j.character_name}
                    </td>
                    <td className="truncate max-w-[90px]" title={pilot}>
                      {samePilot ? "—" : pilot}
                    </td>
                    <td className="truncate max-w-[120px]" title={j.blueprint_name}>
                      {j.blueprint_name}
                    </td>
                    <td className="truncate max-w-[100px]" title={j.output_type_name}>
                      {j.output_type_name || "—"}
                    </td>
                    <td className="capitalize">{j.activity}</td>
                    <td className="truncate max-w-[140px] text-[var(--text-muted)]" title={j.location_name}>
                      {j.location_name || "—"}
                    </td>
                    <td className="num">{j.runs}</td>
                    <td>
                      <span
                        className={clsx(
                          "capitalize",
                          j.status === "active" && "text-[var(--ok)]",
                          j.status === "paused" && "text-[var(--warn)]",
                          j.status === "ready" && "text-[var(--accent)]"
                        )}
                      >
                        {j.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap">{formatEveTime(j.ends_at)}</td>
                    <td className="num whitespace-nowrap">{formatTimeLeft(j.ends_at, j.status, nowMs)}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={10} className="text-[var(--text-muted)] p-2">
                  {jobs.length
                    ? "No jobs match your filters."
                    : "No industry jobs yet — click Sync from ESI (requires esi-industry.read_character_jobs.v1)."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
