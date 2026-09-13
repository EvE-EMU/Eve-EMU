"use client";

import { useMemo, useState } from "react";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { formatEveTime } from "@/lib/eveTime";

export type WalletJournalRow = {
  ref_type: string;
  amount: string;
  balance: string;
  reason: string;
  recorded_at: string;
  character_id?: number;
  character_name?: string;
};

type SortKey = "date" | "type" | "amount" | "balance" | "reason";

function fmtIsk(value: string | number) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e12) return `${(n / 1e12).toFixed(2)} T`;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function sortRows(rows: WalletJournalRow[], key: SortKey, asc: boolean): WalletJournalRow[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "date") {
      const ta = Date.parse(a.recorded_at) || 0;
      const tb = Date.parse(b.recorded_at) || 0;
      return (ta - tb) * dir;
    }
    if (key === "type") {
      return a.ref_type.localeCompare(b.ref_type) * dir;
    }
    if (key === "reason") {
      return (a.reason || "").localeCompare(b.reason || "") * dir;
    }
    if (key === "amount") {
      return (Number(a.amount) - Number(b.amount)) * dir;
    }
    return (Number(a.balance) - Number(b.balance)) * dir;
  });
}

export function CharacterSheetWallet({ journal }: { journal: WalletJournalRow[] }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortAsc, setSortAsc] = useState(false);
  const [typeFilter, setTypeFilter] = useState("");
  const [flowFilter, setFlowFilter] = useState<"all" | "in" | "out">("all");

  const refTypes = useMemo(() => {
    const set = new Set(journal.map((j) => j.ref_type).filter(Boolean));
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [journal]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = journal.filter((j) => {
      if (typeFilter && j.ref_type !== typeFilter) return false;
      const amount = Number(j.amount);
      if (flowFilter === "in" && !(amount > 0)) return false;
      if (flowFilter === "out" && !(amount < 0)) return false;
      if (!q) return true;
      const hay = [
        j.character_name,
        j.ref_type,
        j.reason,
        j.amount,
        j.balance,
        formatEveTime(j.recorded_at),
        j.recorded_at,
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    filtered = sortRows(filtered, sortKey, sortAsc);
    return filtered;
  }, [journal, query, sortKey, sortAsc, typeFilter, flowFilter]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(key === "type" || key === "reason");
    }
  };

  if (!journal.length) {
    return <p className="text-[var(--text-muted)]">No wallet journal entries synced yet.</p>;
  }

  const showPilot = journal.some((j) => j.character_name);

  return (
    <div className="eve-char-sheet-wallet">
      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Filter date, type, reason, amount…"
        shown={rows.length}
        total={journal.length}
        filters={
          <>
            <select
              className="eve-input"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by transaction type"
            >
              <option value="">All types</option>
              {refTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              className="eve-input"
              value={flowFilter}
              onChange={(e) => setFlowFilter(e.target.value as "all" | "in" | "out")}
              aria-label="Filter by flow"
            >
              <option value="all">In + out</option>
              <option value="in">Incoming only</option>
              <option value="out">Outgoing only</option>
            </select>
          </>
        }
      />

      <div className="eve-scroll eve-char-sheet-wallet-table-wrap">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              {showPilot ? <th>Pilot</th> : null}
              <th>
                <CharSheetSortButton
                  label="Date"
                  active={sortKey === "date"}
                  asc={sortAsc}
                  onClick={() => toggleSort("date")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Type"
                  active={sortKey === "type"}
                  asc={sortAsc}
                  onClick={() => toggleSort("type")}
                />
              </th>
              <th className="text-right">
                <CharSheetSortButton
                  label="Amount"
                  active={sortKey === "amount"}
                  asc={sortAsc}
                  align="right"
                  onClick={() => toggleSort("amount")}
                />
              </th>
              <th className="text-right">
                <CharSheetSortButton
                  label="Balance"
                  active={sortKey === "balance"}
                  asc={sortAsc}
                  align="right"
                  onClick={() => toggleSort("balance")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Reason"
                  active={sortKey === "reason"}
                  asc={sortAsc}
                  onClick={() => toggleSort("reason")}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((j, i) => (
                <tr key={`${j.character_id ?? ""}-${j.recorded_at}-${j.ref_type}-${j.amount}-${i}`}>
                  {showPilot ? <td className="whitespace-nowrap">{j.character_name || "—"}</td> : null}
                  <td className="whitespace-nowrap">{formatEveTime(j.recorded_at)}</td>
                  <td>{j.ref_type || "—"}</td>
                  <td
                    className={`text-right tabular-nums ${Number(j.amount) >= 0 ? "text-[var(--ok)]" : "text-[var(--danger)]"}`}
                  >
                    {fmtIsk(j.amount)}
                  </td>
                  <td className="text-right tabular-nums">{fmtIsk(j.balance)}</td>
                  <td className="max-w-[220px] truncate" title={j.reason}>
                    {j.reason || "—"}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="text-[var(--text-muted)]">
                  No entries match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
