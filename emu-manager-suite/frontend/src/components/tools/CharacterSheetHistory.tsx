"use client";

import { useMemo, useState } from "react";
import { CharSheetOrgLink } from "@/components/tools/CharSheetOrgLink";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { formatEveTime } from "@/lib/eveTime";

export type CorpHistoryRow = {
  corporation_id: number;
  corporation_name: string;
  record_id?: number | null;
  joined_at?: string | null;
  left_at?: string | null;
  is_current?: boolean;
};

type SortKey = "joined" | "left" | "corp";

function sortRows(rows: CorpHistoryRow[], key: SortKey, asc: boolean): CorpHistoryRow[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "corp") return a.corporation_name.localeCompare(b.corporation_name) * dir;
    if (key === "joined") {
      const ta = Date.parse(a.joined_at || "") || 0;
      const tb = Date.parse(b.joined_at || "") || 0;
      return (ta - tb) * dir;
    }
    const ta = a.is_current ? Number.MAX_SAFE_INTEGER : Date.parse(a.left_at || "") || 0;
    const tb = b.is_current ? Number.MAX_SAFE_INTEGER : Date.parse(b.left_at || "") || 0;
    return (ta - tb) * dir;
  });
}

export function CharacterSheetHistory({ history }: { history: CorpHistoryRow[] }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("joined");
  const [sortAsc, setSortAsc] = useState(false);
  const [currentOnly, setCurrentOnly] = useState(false);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = history.filter((r) => {
      if (currentOnly && !r.is_current) return false;
      if (!q) return true;
      const hay = [r.corporation_name, formatEveTime(r.joined_at), formatEveTime(r.left_at), r.joined_at, r.left_at]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortRows(filtered, sortKey, sortAsc);
  }, [history, query, currentOnly, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "corp");
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-[10px] text-[var(--text-muted)]">
        Corporation membership from ESI public history — join dates and inferred leave dates when the character moved to another corp.
      </p>

      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Search corporation…"
        filters={
          <label className="eve-char-sheet-filter-check">
            <input type="checkbox" checked={currentOnly} onChange={(e) => setCurrentOnly(e.target.checked)} />
            Current corp only
          </label>
        }
        shown={rows.length}
        total={history.length}
      />

      <div className="eve-char-sheet-table-wrap">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th>
                <CharSheetSortButton label="Corporation" active={sortKey === "corp"} asc={sortAsc} onClick={() => toggleSort("corp")} />
              </th>
              <th>
                <CharSheetSortButton label="Joined" active={sortKey === "joined"} asc={sortAsc} onClick={() => toggleSort("joined")} />
              </th>
              <th>
                <CharSheetSortButton label="Left" active={sortKey === "left"} asc={sortAsc} onClick={() => toggleSort("left")} />
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-[var(--text-muted)]">
                  No corporation history — sync character to refresh.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={`${r.corporation_id}-${r.joined_at}`}>
                  <td>
                    <CharSheetOrgLink corpId={r.corporation_id} corpName={r.corporation_name} />
                  </td>
                  <td>{formatEveTime(r.joined_at)}</td>
                  <td>{r.is_current ? "—" : formatEveTime(r.left_at)}</td>
                  <td>{r.is_current ? <span className="text-[var(--ok)]">Current</span> : "Former"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
