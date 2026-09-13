"use client";

import { useCallback, useEffect, useMemo, useState, Fragment } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { KpiStrip, KpiTile, SectionHead } from "@/components/ui";
import { CharSheetSortButton } from "@/components/tools/CharSheetTableToolbar";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { characterPortraitUrl } from "@/lib/evetech";
import { formatEveTime } from "@/lib/eveTime";
import { sortByKey, useTableSort } from "@/lib/useTableSort";

type KillboardRow = {
  character_id: number;
  character_name: string;
  kills: number;
  losses: number;
  isk_destroyed: string | number;
  isk_lost: string | number;
};

type KillboardStats = {
  isk_destroyed?: number;
  isk_lost?: number;
  ships_destroyed?: number;
  ships_lost?: number;
  error?: string;
};

type RecentKill = {
  killmail_id: number;
  killmail_hash?: string;
  killed_at?: string | null;
  outcome: string;
  solar_system_id?: number | null;
  solar_system_name?: string | null;
  ship_type_id?: number | null;
  ship_type_name?: string | null;
  total_value?: number;
  pilot_character_id?: number | null;
  pilot_character_name?: string | null;
  victim_character_id?: number | null;
  victim_character_name?: string | null;
  attackers?: {
    character_id?: number | null;
    character_name?: string | null;
    damage_done?: number;
    final_blow?: boolean;
  }[];
  zkill_url?: string;
  source?: string;
};

type PilotDetail = {
  character_id: number;
  character_name: string;
  kills: number;
  losses: number;
  isk_destroyed: number;
  isk_lost: number;
  recent_kills: RecentKill[];
  in_roster?: boolean;
  zkill_url?: string;
};

function fmtIsk(v: string | number | null | undefined) {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return String(v);
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function openCharacterSheet(characterId: number) {
  window.dispatchEvent(
    new CustomEvent("emums:inspect-character", { detail: { character_id: characterId } })
  );
}

const BAR_COLORS = ["#8b1a1a", "#a02828", "#b83838", "#c84848", "#d85858"];

function PilotNameButton({
  characterId,
  name,
  className,
  onSelect,
}: {
  characterId?: number | null;
  name?: string | null;
  className?: string;
  onSelect?: (characterId: number) => void;
}) {
  if (!characterId || !name) return <span className="text-[var(--text-muted)]">—</span>;
  return (
    <button
      type="button"
      className={className ?? "eve-char-sheet-link text-left"}
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.(characterId);
      }}
      title="View pilot details"
    >
      {name}
    </button>
  );
}

function KillDetailRow({
  kill,
  onClose,
  onSelectPilot,
}: {
  kill: RecentKill;
  onClose: () => void;
  onSelectPilot: (characterId: number) => void;
}) {
  const inspect = useCharSheetInspect();
  const attackers = (kill.attackers ?? []).filter((a) => a.character_id);

  return (
    <tr className="eve-killboard-detail-row">
      <td colSpan={7} className="!p-0">
        <div className="eve-killboard-detail border-t border-[var(--border)] bg-[var(--panel-elevated)] p-2 space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">Killmail</div>
              <div className="font-mono text-[11px]">#{kill.killmail_id}</div>
            </div>
            <div className="flex gap-2">
              {kill.zkill_url ? (
                <a href={kill.zkill_url} target="_blank" rel="noreferrer" className="eve-btn-sm">
                  zKillboard
                </a>
              ) : null}
              <button type="button" className="eve-btn-sm" onClick={onClose}>
                Close
              </button>
            </div>
          </div>

          <dl className="eve-char-sheet-dl grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
            <div>
              <dt>Time</dt>
              <dd>{formatEveTime(kill.killed_at)}</dd>
            </div>
            <div>
              <dt>Value</dt>
              <dd className="font-mono">{fmtIsk(kill.total_value)}</dd>
            </div>
            <div>
              <dt>Ship</dt>
              <dd className="inline-flex items-center gap-1">
                {kill.ship_type_id ? <EveTypeIcon typeId={kill.ship_type_id} size={18} /> : null}
                {kill.ship_type_name || "—"}
              </dd>
            </div>
            <div>
              <dt>System</dt>
              <dd>
                {kill.solar_system_id && inspect?.openSystemDetail ? (
                  <button
                    type="button"
                    className="eve-char-sheet-link"
                    onClick={() =>
                      inspect.openSystemDetail(kill.solar_system_id!, kill.solar_system_name || undefined)
                    }
                  >
                    {kill.solar_system_name || `System ${kill.solar_system_id}`}
                  </button>
                ) : (
                  kill.solar_system_name || "—"
                )}
              </dd>
            </div>
            <div>
              <dt>{kill.outcome === "loss" ? "Lost by" : "Final blow"}</dt>
              <dd>
                <PilotNameButton
                  characterId={kill.pilot_character_id}
                  name={kill.pilot_character_name}
                  onSelect={onSelectPilot}
                />
              </dd>
            </div>
            <div>
              <dt>Victim</dt>
              <dd>
                <PilotNameButton
                  characterId={kill.victim_character_id}
                  name={kill.victim_character_name}
                  onSelect={onSelectPilot}
                />
              </dd>
            </div>
          </dl>

          {attackers.length ? (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">
                Attackers ({attackers.length})
              </div>
              <ul className="text-[10px] space-y-0.5 max-h-24 overflow-y-auto eve-scroll">
                {attackers.slice(0, 12).map((a) => (
                  <li key={a.character_id} className="flex items-center gap-2">
                    <img src={characterPortraitUrl(a.character_id!, 32)} alt="" width={16} height={16} />
                    <PilotNameButton characterId={a.character_id} name={a.character_name} onSelect={onSelectPilot} />
                    {a.final_blow ? <span className="text-[var(--accent)]">FB</span> : null}
                    <span className="text-[var(--text-muted)] font-mono ml-auto">
                      {a.damage_done?.toLocaleString() ?? 0}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function PilotDetailPanel({
  pilot,
  onClose,
  onSelectPilot,
}: {
  pilot: PilotDetail;
  onClose: () => void;
  onSelectPilot: (characterId: number) => void;
}) {
  return (
    <div className="eve-killboard-pilot-detail border border-[var(--border)] bg-[var(--panel-elevated)] p-2 space-y-2">
      <div className="flex items-start gap-2">
        <img src={characterPortraitUrl(pilot.character_id, 128)} alt="" width={48} height={48} className="rounded" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[12px] font-semibold truncate">{pilot.character_name}</h3>
            {pilot.in_roster ? (
              <span className="text-[9px] uppercase tracking-wide text-[var(--ok)]">Roster</span>
            ) : null}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] font-mono">
            {pilot.kills}K / {pilot.losses}L · {fmtIsk(pilot.isk_destroyed)} destroyed · {fmtIsk(pilot.isk_lost)} lost
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <button type="button" className="eve-btn-sm" onClick={() => openCharacterSheet(pilot.character_id)}>
            Char sheet
          </button>
          {pilot.zkill_url ? (
            <a href={pilot.zkill_url} target="_blank" rel="noreferrer" className="eve-btn-sm text-center">
              zKill
            </a>
          ) : null}
          <button type="button" className="eve-btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      {pilot.recent_kills.length ? (
        <div className="overflow-x-auto eve-scroll">
          <table className="eve-table text-[10px] min-w-full">
            <thead>
              <tr>
                <th>When</th>
                <th>Outcome</th>
                <th>Ship</th>
                <th>Victim / Pilot</th>
                <th>ISK</th>
              </tr>
            </thead>
            <tbody>
              {pilot.recent_kills.map((k) => (
                <tr key={k.killmail_id} className={k.outcome === "kill" ? "eve-combat-kill" : "eve-combat-loss"}>
                  <td>{formatEveTime(k.killed_at)}</td>
                  <td>
                    <span className={`eve-combat-badge ${k.outcome}`}>{k.outcome === "kill" ? "Kill" : "Loss"}</span>
                  </td>
                  <td>{k.ship_type_name || "—"}</td>
                  <td>
                    {k.outcome === "kill" ? (
                      <PilotNameButton
                        characterId={k.victim_character_id}
                        name={k.victim_character_name}
                        onSelect={onSelectPilot}
                      />
                    ) : (
                      <span className="text-[var(--text-muted)]">Ship loss</span>
                    )}
                  </td>
                  <td className="font-mono">{fmtIsk(k.total_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-[10px] text-[var(--text-muted)]">No recent killmails for this pilot.</p>
      )}
    </div>
  );
}

export function KillboardPanel({ initialRows }: { initialRows: KillboardRow[] }) {
  const [tab, setTab] = useState<"recent" | "leaderboard">("recent");
  const [rows, setRows] = useState(initialRows);
  const [recent, setRecent] = useState<RecentKill[]>([]);
  const [stats, setStats] = useState<KillboardStats | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKillId, setExpandedKillId] = useState<number | null>(null);
  const [pilotDetail, setPilotDetail] = useState<PilotDetail | null>(null);
  const [loadingPilot, setLoadingPilot] = useState(false);

  type SortKey = "pilot" | "kills" | "losses" | "isk_destroyed" | "isk_lost";
  const { sortKey, sortAsc, toggleSort } = useTableSort<SortKey>("isk_destroyed", false);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch("/api/tools/killboard/stats", { cache: "no-store" });
      if (res.ok) setStats((await res.json()) as KillboardStats);
    } catch {
      /* optional KPI strip */
    }
  }, []);

  const loadRecent = useCallback(async () => {
    setLoadingRecent(true);
    try {
      const res = await fetch("/api/tools/killboard/recent?limit=50", { cache: "no-store" });
      if (res.ok) {
        setRecent((await res.json()) as RecentKill[]);
      }
    } catch {
      /* keep prior rows */
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  const loadPilot = useCallback(async (characterId: number) => {
    setLoadingPilot(true);
    try {
      const res = await fetch(`/api/tools/killboard/pilot/${characterId}`, { cache: "no-store" });
      if (res.ok) {
        setPilotDetail((await res.json()) as PilotDetail);
      }
    } catch {
      setPilotDetail(null);
    } finally {
      setLoadingPilot(false);
    }
  }, []);

  const sync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      const res = await fetch("/api/tools/killboard/sync", { method: "POST", cache: "no-store" });
      if (!res.ok) {
        setError("Killboard sync failed — zKill may be rate-limited.");
        return;
      }
      const data = (await res.json()) as { leaderboard?: KillboardRow[] };
      setRows(data.leaderboard ?? []);
      await Promise.all([loadStats(), loadRecent()]);
    } catch {
      setError("Killboard sync failed.");
    } finally {
      setSyncing(false);
    }
  }, [loadStats, loadRecent]);

  useEffect(() => {
    void loadStats();
    void loadRecent();
  }, [loadStats, loadRecent]);

  useEffect(() => {
    if (!initialRows.length) {
      void sync();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectPilot = useCallback(
    (characterId: number) => {
      void loadPilot(characterId);
    },
    [loadPilot]
  );

  const sorted = useMemo(
    () =>
      sortByKey(rows, sortKey, sortAsc, (row, key) => {
        if (key === "pilot") return row.character_name;
        if (key === "kills") return row.kills;
        if (key === "losses") return row.losses;
        if (key === "isk_destroyed") return parseFloat(String(row.isk_destroyed)) || 0;
        return parseFloat(String(row.isk_lost)) || 0;
      }),
    [rows, sortKey, sortAsc]
  );

  const chartData = useMemo(
    () =>
      sorted.slice(0, 8).map((r) => ({
        name: r.character_name.split(" ")[0],
        isk: parseFloat(String(r.isk_destroyed)) || 0,
      })),
    [sorted]
  );

  return (
    <div className="text-[11px] space-y-2 p-1">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1">
          <SectionHead>Killboard</SectionHead>
          <p className="text-[10px] text-[var(--text-muted)]">
            Recent coalition kills and losses — click a pilot for stats, expand a row for killmail detail.
          </p>
        </div>
        <button type="button" className="eve-btn-sm" disabled={syncing} onClick={() => void sync()}>
          {syncing ? "Syncing…" : "Sync zKill"}
        </button>
      </div>

      <div className="eve-char-sheet-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "recent"}
          className={tab === "recent" ? "active" : ""}
          onClick={() => setTab("recent")}
        >
          Recent kills
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "leaderboard"}
          className={tab === "leaderboard" ? "active" : ""}
          onClick={() => setTab("leaderboard")}
        >
          Leaderboard
        </button>
      </div>

      {error ? <p className="text-[var(--danger)]">{error}</p> : null}

      {stats && !stats.error ? (
        <KpiStrip>
          <KpiTile label="Alliance Kills" value={String(stats.ships_destroyed ?? "—")} tone="accent" />
          <KpiTile label="Alliance Losses" value={String(stats.ships_lost ?? "—")} />
          <KpiTile label="ISK Destroyed" value={fmtIsk(stats.isk_destroyed)} tone="ok" />
          <KpiTile label="ISK Lost" value={fmtIsk(stats.isk_lost)} tone="warn" />
        </KpiStrip>
      ) : null}

      {loadingPilot ? (
        <p className="text-[10px] text-[var(--text-muted)]">Loading pilot…</p>
      ) : pilotDetail ? (
        <PilotDetailPanel pilot={pilotDetail} onClose={() => setPilotDetail(null)} onSelectPilot={selectPilot} />
      ) : null}

      {tab === "recent" ? (
        <div className="overflow-x-auto eve-scroll">
          <table className="eve-table text-[10px] min-w-full">
            <thead>
              <tr>
                <th>When</th>
                <th />
                <th>Outcome</th>
                <th>Ship</th>
                <th>Pilot</th>
                <th>Victim</th>
                <th>ISK</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((kill) => (
                <Fragment key={kill.killmail_id}>
                  <tr
                    className={`cursor-pointer hover:bg-[var(--panel-elevated)] ${
                      kill.outcome === "kill" ? "eve-combat-kill" : "eve-combat-loss"
                    } ${expandedKillId === kill.killmail_id ? "eve-killboard-row-expanded" : ""}`}
                    onClick={() =>
                      setExpandedKillId((id) => (id === kill.killmail_id ? null : kill.killmail_id))
                    }
                  >
                    <td className="whitespace-nowrap">{formatEveTime(kill.killed_at)}</td>
                    <td>
                      {kill.ship_type_id ? <EveTypeIcon typeId={kill.ship_type_id} size={20} /> : null}
                    </td>
                    <td>
                      <span className={`eve-combat-badge ${kill.outcome}`}>
                        {kill.outcome === "kill" ? "Kill" : "Loss"}
                      </span>
                    </td>
                    <td className="max-w-[8rem] truncate">{kill.ship_type_name || "—"}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <PilotNameButton
                        characterId={kill.pilot_character_id}
                        name={kill.pilot_character_name}
                        onSelect={selectPilot}
                      />
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <PilotNameButton
                        characterId={kill.victim_character_id}
                        name={kill.victim_character_name}
                        onSelect={selectPilot}
                      />
                    </td>
                    <td className="font-mono whitespace-nowrap">{fmtIsk(kill.total_value)}</td>
                  </tr>
                  {expandedKillId === kill.killmail_id ? (
                    <KillDetailRow
                      kill={kill}
                      onClose={() => setExpandedKillId(null)}
                      onSelectPilot={selectPilot}
                    />
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
          {!recent.length && !loadingRecent && !syncing ? (
            <p className="text-[10px] text-[var(--text-muted)] p-2">
              No recent kills loaded. Click <strong>Sync zKill</strong> or check zKill rate limits.
            </p>
          ) : null}
          {loadingRecent ? <p className="text-[10px] text-[var(--text-muted)] p-2">Loading recent kills…</p> : null}
        </div>
      ) : (
        <>
          {chartData.length ? (
            <div className="eve-chart-3d h-40 w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                  <CartesianGrid stroke="#2a3540" strokeDasharray="2 2" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#9ab0c0", fontSize: 9 }} />
                  <YAxis tick={{ fill: "#9ab0c0", fontSize: 9 }} tickFormatter={(v) => fmtIsk(v)} width={48} />
                  <Tooltip
                    contentStyle={{ background: "#12181f", border: "1px solid #2a3540", fontSize: 10 }}
                    formatter={(v) => [fmtIsk(v as number), "ISK destroyed"]}
                  />
                  <Bar dataKey="isk" radius={[2, 2, 0, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          <div className="overflow-x-auto eve-scroll">
            <table className="eve-table text-[10px] min-w-full">
              <thead>
                <tr>
                  <th />
                  <th>
                    <CharSheetSortButton
                      label="Pilot"
                      active={sortKey === "pilot"}
                      asc={sortAsc}
                      onClick={() => toggleSort("pilot")}
                    />
                  </th>
                  <th>
                    <CharSheetSortButton label="K" active={sortKey === "kills"} asc={sortAsc} onClick={() => toggleSort("kills")} />
                  </th>
                  <th>
                    <CharSheetSortButton label="L" active={sortKey === "losses"} asc={sortAsc} onClick={() => toggleSort("losses")} />
                  </th>
                  <th>
                    <CharSheetSortButton
                      label="ISK Destroyed"
                      active={sortKey === "isk_destroyed"}
                      asc={sortAsc}
                      onClick={() => toggleSort("isk_destroyed")}
                    />
                  </th>
                  <th>
                    <CharSheetSortButton
                      label="ISK Lost"
                      active={sortKey === "isk_lost"}
                      asc={sortAsc}
                      onClick={() => toggleSort("isk_lost")}
                    />
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((row) => (
                  <tr key={row.character_id}>
                    <td>
                      <img src={characterPortraitUrl(row.character_id, 64)} alt="" width={24} height={24} />
                    </td>
                    <td>
                      <PilotNameButton
                        characterId={row.character_id}
                        name={row.character_name}
                        onSelect={selectPilot}
                      />
                    </td>
                    <td className="font-mono">{row.kills}</td>
                    <td className="font-mono">{row.losses}</td>
                    <td className="font-mono">{fmtIsk(row.isk_destroyed)}</td>
                    <td className="font-mono">{fmtIsk(row.isk_lost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!sorted.length && !syncing ? (
              <p className="text-[10px] text-[var(--text-muted)] p-2">
                No killboard data yet. Click <strong>Sync zKill</strong> to pull alliance stats.
              </p>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
