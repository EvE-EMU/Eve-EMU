"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { characterPortraitUrl } from "@/lib/evetech";
import { fmtIskCompact } from "@/lib/iskFormat";
import { KpiStrip, KpiTile, SectionHead } from "@/components/ui";
import { CharacterSheetWallet, type WalletJournalRow } from "@/components/tools/CharacterSheetWallet";
import { InteractionAuditPanel } from "@/components/tools/InteractionAuditPanel";

export type RosterCharacterRow = {
  character_id: number;
  character_name: string;
  is_main: boolean;
  token_valid: boolean;
  corporation_name: string;
  wallet_balance_isk: string;
  assets_value_isk: string;
  skill_points: number;
  asset_item_count: number;
  current_location: string | null;
  last_sync_at: string | null;
  last_sync_eve: string | null;
  open_flags: number;
};

export type RosterOverview = {
  character_count: number;
  totals: {
    wallet_balance_isk: string;
    assets_value_isk: string;
    skill_points: number;
    asset_item_count: number;
    open_flags: number;
  };
  characters: RosterCharacterRow[];
  combined_wallet_journal: (WalletJournalRow & { character_id: number; character_name: string })[];
  combined_flags: {
    character_id: number;
    character_name: string;
    flag_key: string;
    severity: string;
    detail: string;
  }[];
  interaction_summary?: {
    counterparty_count: number;
    interaction_events: number;
    top_counterparties: {
      counterparty_id: number;
      counterparty_name: string;
      counterparty_kind: string;
      event_count: number;
    }[];
  };
};

type SortKey = "name" | "wallet" | "assets" | "sp" | "items" | "flags" | "sync";

type RosterCombinedPanelProps = {
  onSelectCharacter: (characterId: number) => void;
};

export function RosterCombinedPanel({ onSelectCharacter }: RosterCombinedPanelProps) {
  const [overview, setOverview] = useState<RosterOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncQueued, setSyncQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("wallet");
  const [sortAsc, setSortAsc] = useState(false);
  const [tab, setTab] = useState<"roster" | "wallet" | "flags" | "interactions">("roster");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/audit/roster", { cache: "no-store", credentials: "same-origin" });
      if (!res.ok) {
        setOverview(null);
        setError("Unable to load roster overview.");
        return;
      }
      setOverview((await res.json()) as RosterOverview);
    } catch {
      setError("Unable to load roster overview.");
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const syncAll = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/audit/roster", { method: "POST", credentials: "same-origin" });
      if (res.ok) {
        const data = (await res.json()) as { status?: string; overview?: RosterOverview };
        if (data.status === "queued") {
          setSyncQueued(true);
          setError(null);
          window.setTimeout(() => {
            setSyncQueued(false);
            void load();
          }, 8000);
          return;
        }
        setSyncQueued(false);
        if (data.overview) setOverview(data.overview);
        else await load();
      }
    } finally {
      setSyncing(false);
    }
  }, [load]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    if (!overview) return [];
    const q = query.trim().toLowerCase();
    let list = overview.characters.filter((c) => {
      if (!q) return true;
      return (
        c.character_name.toLowerCase().includes(q) ||
        c.corporation_name.toLowerCase().includes(q) ||
        (c.current_location || "").toLowerCase().includes(q)
      );
    });
    const dir = sortAsc ? 1 : -1;
    list = [...list].sort((a, b) => {
      if (sortKey === "name") return a.character_name.localeCompare(b.character_name) * dir;
      if (sortKey === "wallet") return (Number(a.wallet_balance_isk) - Number(b.wallet_balance_isk)) * dir;
      if (sortKey === "assets") return (Number(a.assets_value_isk) - Number(b.assets_value_isk)) * dir;
      if (sortKey === "sp") return (a.skill_points - b.skill_points) * dir;
      if (sortKey === "items") return (a.asset_item_count - b.asset_item_count) * dir;
      if (sortKey === "flags") return (a.open_flags - b.open_flags) * dir;
      const ta = Date.parse(a.last_sync_at || "") || 0;
      const tb = Date.parse(b.last_sync_at || "") || 0;
      return (ta - tb) * dir;
    });
    return list;
  }, [overview, query, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "name");
    }
  };

  if (loading && !overview) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">Loading combined roster…</p>;
  }

  if (error || !overview) {
    return (
      <div className="p-3 text-[11px]">
        <p className="text-[var(--text-muted)]">{error ?? "No roster data."}</p>
        <button type="button" className="eve-btn-sm mt-2" onClick={() => void load()}>
          Retry
        </button>
      </div>
    );
  }

  const SortTh = ({ label, col }: { label: string; col: SortKey }) => (
    <th>
      <button type="button" className="eve-roster-sort-btn" onClick={() => toggleSort(col)}>
        {label}
        {sortKey === col ? (sortAsc ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <div className="eve-roster-combined">
      <div className="eve-roster-combined-toolbar">
        <div>
          <h2 className="eve-roster-combined-title">All characters</h2>
          <p className="text-[10px] text-[var(--text-muted)]">
            Combined view across {overview.character_count} linked pilots — no session switch needed
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button type="button" className="eve-btn-sm" disabled={loading} onClick={() => void load()}>
            Refresh
          </button>
          <button
            type="button"
            className="eve-btn-sm eve-btn-primary"
            disabled={syncing}
            onClick={() => void syncAll()}
          >
            {syncing ? (syncQueued ? "Sync queued…" : "Syncing all…") : "Sync all alts"}
          </button>
        </div>
      </div>

      <KpiStrip>
        <KpiTile label="Total wallet" value={`${fmtIskCompact(overview.totals.wallet_balance_isk)} ISK`} />
        <KpiTile label="Assets (est.)" value={`${fmtIskCompact(overview.totals.assets_value_isk)} ISK`} />
        <KpiTile label="Skill points" value={overview.totals.skill_points.toLocaleString()} />
        <KpiTile label="Asset lines" value={overview.totals.asset_item_count.toLocaleString()} />
        {overview.totals.open_flags ? (
          <KpiTile label="Open flags" value={String(overview.totals.open_flags)} tone="warn" />
        ) : null}
        {overview.interaction_summary ? (
          <KpiTile
            label="Interactions"
            value={overview.interaction_summary.interaction_events.toLocaleString()}
            tone="accent"
          />
        ) : null}
      </KpiStrip>

      <div className="eve-char-sheet-tabs mt-2" role="tablist">
        {(
          [
            ["roster", `Roster (${overview.character_count})`],
            ["wallet", "Combined wallet"],
            ["flags", `Flags (${overview.combined_flags.length})`],
            ["interactions", "Interaction audit"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={clsx(tab === id && "active")}
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "roster" ? (
        <div className="eve-roster-table-wrap mt-2">
          <input
            type="search"
            className="eve-input w-full mb-2"
            placeholder="Filter by name, corp, or location…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <p className="text-[10px] text-[var(--text-muted)] mb-1">
            Showing {rows.length} of {overview.character_count} — click a row for full character sheet
          </p>
          <table className="eve-table eve-roster-table text-[10px]">
            <thead>
              <tr>
                <th />
                <SortTh label="Pilot" col="name" />
                <th>Corp</th>
                <SortTh label="Wallet" col="wallet" />
                <SortTh label="Assets" col="assets" />
                <SortTh label="SP" col="sp" />
                <SortTh label="Items" col="items" />
                <th>Location</th>
                <SortTh label="Sync" col="sync" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.character_id}
                  className={clsx("eve-roster-row", !row.token_valid && "is-stale-token")}
                  onClick={() => onSelectCharacter(row.character_id)}
                >
                  <td>
                    <img src={characterPortraitUrl(row.character_id, 64)} alt="" width={24} height={24} />
                  </td>
                  <td>
                    <strong>{row.character_name}</strong>
                    {row.is_main ? <span className="eve-alt-badge ml-1">Main</span> : null}
                    {!row.token_valid ? <span className="eve-alt-badge warn ml-1">Re-link</span> : null}
                    {row.open_flags ? (
                      <span className="eve-alt-badge warn ml-1">{row.open_flags} flag</span>
                    ) : null}
                  </td>
                  <td className="text-[var(--text-muted)]">{row.corporation_name || "—"}</td>
                  <td className="num">{fmtIskCompact(row.wallet_balance_isk)}</td>
                  <td className="num">{fmtIskCompact(row.assets_value_isk)}</td>
                  <td className="num">{row.skill_points.toLocaleString()}</td>
                  <td className="num">{row.asset_item_count.toLocaleString()}</td>
                  <td className="truncate max-w-[120px]">{row.current_location || "—"}</td>
                  <td className="text-[var(--text-muted)]">{row.last_sync_eve || "Never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {tab === "wallet" ? (
        <div className="mt-2">
          <SectionHead>Recent transactions — all linked characters</SectionHead>
          <CharacterSheetWallet journal={overview.combined_wallet_journal} />
        </div>
      ) : null}

      {tab === "flags" ? (
        <ul className="eve-roster-flags mt-2 text-[10px]">
          {overview.combined_flags.length === 0 ? (
            <li className="text-[var(--text-muted)]">No open audit flags across your roster.</li>
          ) : (
            overview.combined_flags.map((f, i) => (
              <li key={`${f.character_id}-${f.flag_key}-${i}`} className={clsx("eve-roster-flag", f.severity)}>
                <button type="button" className="eve-roster-flag-link" onClick={() => onSelectCharacter(f.character_id)}>
                  {f.character_name}
                </button>
                <span className="font-medium">{f.flag_key}</span>
                <span className="text-[var(--text-muted)]">{f.detail}</span>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {tab === "interactions" ? (
        <div className="mt-2">
          {overview.interaction_summary?.top_counterparties.length ? (
            <p className="text-[10px] text-[var(--text-muted)] mb-2">
              Top contacts:{" "}
              {overview.interaction_summary.top_counterparties
                .slice(0, 5)
                .map((c) => `${c.counterparty_name} (${c.event_count})`)
                .join(" · ")}
            </p>
          ) : null}
          <InteractionAuditPanel />
        </div>
      ) : null}
    </div>
  );
}
