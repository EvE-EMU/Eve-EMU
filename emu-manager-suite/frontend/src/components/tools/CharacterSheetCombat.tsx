"use client";

import { useMemo, useState } from "react";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { formatEveTime } from "@/lib/eveTime";

export type CombatLogRow = {
  killmail_id: number;
  killmail_hash?: string;
  outcome: "kill" | "loss";
  killed_at?: string | null;
  solar_system_id?: number | null;
  solar_system_name?: string | null;
  ship_type_id?: number | null;
  ship_type_name?: string | null;
  victim_character_id?: number | null;
  victim_character_name?: string | null;
  zkill_url?: string;
};

type SortKey = "date" | "outcome" | "ship" | "victim" | "system";

function sortRows(rows: CombatLogRow[], key: SortKey, asc: boolean): CombatLogRow[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "date") {
      const ta = Date.parse(a.killed_at || "") || 0;
      const tb = Date.parse(b.killed_at || "") || 0;
      return (ta - tb) * dir;
    }
    if (key === "outcome") return a.outcome.localeCompare(b.outcome) * dir;
    if (key === "ship") return (a.ship_type_name || "").localeCompare(b.ship_type_name || "") * dir;
    if (key === "victim") {
      return (a.victim_character_name || "").localeCompare(b.victim_character_name || "") * dir;
    }
    return (a.solar_system_name || "").localeCompare(b.solar_system_name || "") * dir;
  });
}

export function CharacterSheetCombat({ combatLog }: { combatLog: CombatLogRow[] }) {
  const inspect = useCharSheetInspect();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortAsc, setSortAsc] = useState(false);
  const [outcomeFilter, setOutcomeFilter] = useState<"all" | "kill" | "loss">("all");

  const kills = combatLog.filter((r) => r.outcome === "kill").length;
  const losses = combatLog.filter((r) => r.outcome === "loss").length;

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = combatLog.filter((r) => {
      if (outcomeFilter !== "all" && r.outcome !== outcomeFilter) return false;
      if (!q) return true;
      const hay = [
        r.outcome,
        r.ship_type_name,
        r.victim_character_name,
        r.solar_system_name,
        formatEveTime(r.killed_at),
        r.killed_at,
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortRows(filtered, sortKey, sortAsc);
  }, [combatLog, query, outcomeFilter, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "ship" || key === "victim" || key === "system");
    }
  };

  return (
    <div className="space-y-3">
      <div className="eve-char-sheet-combat-summary">
        <span className="kill">{kills} kills</span>
        <span className="sep">·</span>
        <span className="loss">{losses} losses</span>
      </div>

      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Search ship, victim, system…"
        filters={
          <select
            className="eve-char-sheet-filter-select"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value as "all" | "kill" | "loss")}
            aria-label="Outcome filter"
          >
            <option value="all">All outcomes</option>
            <option value="kill">Kills only</option>
            <option value="loss">Losses only</option>
          </select>
        }
        shown={rows.length}
        total={combatLog.length}
      />

      <div className="eve-char-sheet-table-wrap">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th>
                <CharSheetSortButton label="Date" active={sortKey === "date"} asc={sortAsc} onClick={() => toggleSort("date")} />
              </th>
              <th>
                <CharSheetSortButton label="Outcome" active={sortKey === "outcome"} asc={sortAsc} onClick={() => toggleSort("outcome")} />
              </th>
              <th>
                <CharSheetSortButton label="Ship" active={sortKey === "ship"} asc={sortAsc} onClick={() => toggleSort("ship")} />
              </th>
              <th>
                <CharSheetSortButton
                  label="Victim / Lost"
                  active={sortKey === "victim"}
                  asc={sortAsc}
                  onClick={() => toggleSort("victim")}
                />
              </th>
              <th>
                <CharSheetSortButton label="System" active={sortKey === "system"} asc={sortAsc} onClick={() => toggleSort("system")} />
              </th>
              <th>zKill</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-[var(--text-muted)]">
                  No combat events in snapshot — sync character or adjust filters.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.killmail_id} className={r.outcome === "kill" ? "eve-combat-kill" : "eve-combat-loss"}>
                  <td>{formatEveTime(r.killed_at)}</td>
                  <td>
                    <span className={`eve-combat-badge ${r.outcome}`}>{r.outcome === "kill" ? "Kill" : "Loss"}</span>
                  </td>
                  <td>
                    {r.ship_type_id ? (
                      <span className="inline-flex items-center gap-1">
                        <EveTypeIcon typeId={r.ship_type_id} size={18} />
                        {r.ship_type_name || `Type ${r.ship_type_id}`}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {r.outcome === "kill"
                      ? r.victim_character_name || (r.victim_character_id ? `Character ${r.victim_character_id}` : "—")
                      : "Your ship"}
                  </td>
                  <td>
                    {r.solar_system_id && inspect?.openSystemDetail ? (
                      <button
                        type="button"
                        className="eve-char-sheet-link"
                        onClick={() => inspect.openSystemDetail(r.solar_system_id!, r.solar_system_name || undefined)}
                      >
                        {r.solar_system_name || `System ${r.solar_system_id}`}
                      </button>
                    ) : (
                      r.solar_system_name || "—"
                    )}
                  </td>
                  <td>
                    {r.zkill_url ? (
                      <a href={r.zkill_url} target="_blank" rel="noreferrer" className="eve-char-sheet-link">
                        View
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
