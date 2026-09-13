"use client";

import { useMemo, useState } from "react";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { formatEveTime } from "@/lib/eveTime";

export type ContractRow = {
  contract_id: number;
  type?: string;
  status?: string;
  title?: string;
  for_corporation?: boolean;
  issuer_corporation_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  start_date?: string | null;
  date_expired?: string | null;
  date_completed?: string | null;
  price?: number | null;
  reward?: number | null;
  collateral?: number | null;
  buyout?: number | null;
};

type SortKey = "id" | "type" | "status" | "title" | "issuer" | "location" | "issued" | "expires" | "value";

function contractValue(c: ContractRow): number {
  const v = c.price ?? c.reward ?? c.buyout ?? c.collateral;
  return v != null && Number.isFinite(v) ? v : 0;
}

function fmtIsk(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function sortContracts(rows: ContractRow[], key: SortKey, asc: boolean): ContractRow[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "id") return (a.contract_id - b.contract_id) * dir;
    if (key === "type") return (a.type || "").localeCompare(b.type || "") * dir;
    if (key === "status") return (a.status || "").localeCompare(b.status || "") * dir;
    if (key === "title") return (a.title || "").localeCompare(b.title || "") * dir;
    if (key === "issuer") return (a.issuer_corporation_name || "").localeCompare(b.issuer_corporation_name || "") * dir;
    if (key === "location") return (a.location_name || "").localeCompare(b.location_name || "") * dir;
    if (key === "issued") {
      const ta = Date.parse(a.start_date || "") || 0;
      const tb = Date.parse(b.start_date || "") || 0;
      return (ta - tb) * dir;
    }
    if (key === "expires") {
      const ta = Date.parse(a.date_expired || "") || 0;
      const tb = Date.parse(b.date_expired || "") || 0;
      return (ta - tb) * dir;
    }
    return (contractValue(a) - contractValue(b)) * dir;
  });
}

export function CharacterSheetContracts({ contracts }: { contracts: ContractRow[] }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("issued");
  const [sortAsc, setSortAsc] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [corpFilter, setCorpFilter] = useState<"all" | "personal" | "corp">("all");

  const statuses = useMemo(() => {
    const set = new Set(contracts.map((c) => c.status).filter(Boolean) as string[]);
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [contracts]);

  const types = useMemo(() => {
    const set = new Set(contracts.map((c) => c.type).filter(Boolean) as string[]);
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [contracts]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = contracts.filter((c) => {
      if (statusFilter && c.status !== statusFilter) return false;
      if (typeFilter && c.type !== typeFilter) return false;
      if (corpFilter === "corp" && !c.for_corporation) return false;
      if (corpFilter === "personal" && c.for_corporation) return false;
      if (!q) return true;
      const value = contractValue(c);
      const hay = [
        c.contract_id,
        c.type,
        c.status,
        c.title,
        c.issuer_corporation_name,
        c.location_name,
        c.start_date,
        c.date_expired,
        c.date_completed,
        value,
        formatEveTime(c.start_date),
        formatEveTime(c.date_expired),
        c.for_corporation ? "corp" : "personal",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortContracts(filtered, sortKey, sortAsc);
  }, [contracts, query, sortKey, sortAsc, statusFilter, typeFilter, corpFilter]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(key === "title" || key === "type" || key === "status");
    }
  };

  if (!contracts.length) {
    return <p className="text-[var(--text-muted)]">No contracts synced yet.</p>;
  }

  return (
    <div className="eve-char-sheet-contracts">
      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Filter ID, type, status, title, issuer…"
        shown={rows.length}
        total={contracts.length}
        filters={
          <>
            <select
              className="eve-input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <select
              className="eve-input"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by type"
            >
              <option value="">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              className="eve-input"
              value={corpFilter}
              onChange={(e) => setCorpFilter(e.target.value as "all" | "personal" | "corp")}
              aria-label="Filter by issuer scope"
            >
              <option value="all">Personal + corp</option>
              <option value="personal">Personal only</option>
              <option value="corp">Corp only</option>
            </select>
          </>
        }
      />

      <div className="eve-scroll eve-char-sheet-wallet-table-wrap">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th>
                <CharSheetSortButton
                  label="ID"
                  active={sortKey === "id"}
                  asc={sortAsc}
                  onClick={() => toggleSort("id")}
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
                  label="Title"
                  active={sortKey === "title"}
                  asc={sortAsc}
                  onClick={() => toggleSort("title")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Issuer"
                  active={sortKey === "issuer"}
                  asc={sortAsc}
                  onClick={() => toggleSort("issuer")}
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
              <th>
                <CharSheetSortButton
                  label="Issued"
                  active={sortKey === "issued"}
                  asc={sortAsc}
                  onClick={() => toggleSort("issued")}
                />
              </th>
              <th>
                <CharSheetSortButton
                  label="Expires"
                  active={sortKey === "expires"}
                  asc={sortAsc}
                  onClick={() => toggleSort("expires")}
                />
              </th>
              <th className="text-right">
                <CharSheetSortButton
                  label="Value"
                  active={sortKey === "value"}
                  asc={sortAsc}
                  align="right"
                  onClick={() => toggleSort("value")}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((c) => {
                const value = c.price ?? c.reward ?? c.buyout ?? c.collateral;
                return (
                  <tr key={c.contract_id}>
                    <td className="tabular-nums">{c.contract_id}</td>
                    <td>{c.type || "—"}</td>
                    <td className={c.status === "outstanding" ? "text-[var(--warn)]" : ""}>{c.status || "—"}</td>
                    <td className="max-w-[140px] truncate" title={c.title}>
                      {c.title || "—"}
                      {c.for_corporation ? <span className="eve-asset-kind-tag">Corp</span> : null}
                    </td>
                    <td>{c.issuer_corporation_name || "—"}</td>
                    <td className="max-w-[120px] truncate" title={c.location_name || undefined}>
                      {c.location_name ||
                        (c.location_id ? `Location ${c.location_id}` : "—")}
                    </td>
                    <td>{formatEveTime(c.start_date)}</td>
                    <td>{formatEveTime(c.date_expired)}</td>
                    <td className="text-right tabular-nums">{fmtIsk(value ?? null)}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={9} className="text-[var(--text-muted)]">
                  No contracts match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
