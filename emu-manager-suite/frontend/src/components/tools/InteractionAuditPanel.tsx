"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { CharSheetSortButton } from "@/components/tools/CharSheetTableToolbar";
import { fmtIskCompact } from "@/lib/iskFormat";
import { sortByKey, useTableSort } from "@/lib/useTableSort";
import { EveTable, KpiStrip, KpiTile, SectionHead, StatusStrip } from "@/components/ui";

export type InteractionRow = {
  counterparty_id: number;
  counterparty_kind: string;
  counterparty_name: string;
  channel: string | null;
  event_count: number;
  total_amount_isk: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_detail: string;
  alt_count: number;
  spy_score?: number;
  recommendation?: string;
  recommendation_label?: string;
  signals?: { key: string; label: string; points: number; detail: string }[];
  tags?: IntelTag[];
  channels?: Record<string, number>;
  blacklisted?: boolean;
  public_links?: Record<string, string>;
};

export type InteractionByCharacter = {
  character_id: number;
  character_name: string;
  channel: string;
  event_count: number;
  total_amount_isk: string;
  last_seen_at: string | null;
  last_detail: string;
};

type IntelTag = {
  id: number;
  tag_type: string;
  label: string;
  tone?: string;
  linked_character_id?: number | null;
  linked_character_name?: string;
  notes?: string;
};

type InteractionResponse = {
  total: number;
  rows: InteractionRow[];
  by_character: InteractionByCharacter[];
  rollup?: boolean;
  detail?: InteractionRow & { spy_score: number };
  tag_types?: Record<string, { label: string; tone: string }>;
};

type SpyMeterRow = InteractionRow & {
  entity_id: number;
  entity_name: string;
  entity_kind: string;
  spy_score: number;
  recommendation: string;
  recommendation_label: string;
  wallet_isk?: number;
};

type SpyMeterResponse = {
  rows: SpyMeterRow[];
  total: number;
  tag_types?: Record<string, { label: string; tone: string }>;
  legend?: { channel: string; label: string; weight: string }[];
};

const KINDS = [
  { value: "", label: "All types" },
  { value: "character", label: "Character" },
  { value: "corporation", label: "Corporation" },
  { value: "alliance", label: "Alliance" },
  { value: "npc", label: "NPC" },
  { value: "structure", label: "Structure" },
];

const CHANNEL_LABELS: Record<string, string> = {
  wallet: "Wallet",
  mail_received: "Mail in",
  mail_sent: "Mail out",
  combat_kill: "Kill",
  combat_loss: "Loss",
  combat_fleet: "Fleet",
  contract: "Contract",
  contact: "Contact",
};

const TAG_OPTIONS = [
  { value: "spy_alt", label: "Spy alt" },
  { value: "known_alt", label: "Known alt" },
  { value: "holding_corp", label: "Holding corp" },
  { value: "hostile", label: "Hostile" },
  { value: "watchlist", label: "Watchlist" },
  { value: "trusted", label: "Trusted" },
];

function kindBadge(kind: string) {
  const tones: Record<string, string> = {
    character: "text-[var(--accent)]",
    corporation: "text-[var(--ok)]",
    alliance: "text-[var(--warn)]",
    npc: "text-[var(--text-muted)]",
    structure: "text-[var(--text-dim)]",
  };
  return <span className={clsx("capitalize text-[10px]", tones[kind] || "")}>{kind}</span>;
}

function fmtWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function scoreTone(score: number) {
  if (score >= 80) return "text-[var(--danger)]";
  if (score >= 55) return "text-[var(--warn)]";
  if (score >= 30) return "text-[var(--accent)]";
  return "text-[var(--text-muted)]";
}

function scoreBar(score: number) {
  const tone =
    score >= 80
      ? "bg-[var(--danger)]"
      : score >= 55
        ? "bg-[var(--warn)]"
        : score >= 30
          ? "bg-[var(--accent)]"
          : "bg-[var(--text-muted)]";
  return (
    <div className="flex items-center gap-1.5 min-w-[72px]">
      <div className="h-1.5 flex-1 bg-[var(--panel-inset)] border border-[var(--edge-dim)]">
        <div className={clsx("h-full", tone)} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className={clsx("font-mono tabular-nums w-8 text-end", scoreTone(score))}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

type RowSortKey = "counterparty" | "kind" | "channel" | "events" | "alts" | "last_seen" | "spy";
type AltSortKey = "pilot" | "channel" | "events";

export function InteractionAuditPanel() {
  const [tab, setTab] = useState<"interactions" | "spy-meter">("interactions");
  const [data, setData] = useState<InteractionResponse | null>(null);
  const [spyData, setSpyData] = useState<SpyMeterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [rollup, setRollup] = useState(true);
  const [minScore, setMinScore] = useState(30);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tagType, setTagType] = useState("spy_alt");
  const [linkCharId, setLinkCharId] = useState("");
  const [linkCharName, setLinkCharName] = useState("");
  const [tagNotes, setTagNotes] = useState("");
  const [tagBusy, setTagBusy] = useState(false);
  const [tagMsg, setTagMsg] = useState("");
  const [detail, setDetail] = useState<InteractionResponse | null>(null);
  const limit = 100;
  const { sortKey, sortAsc, toggleSort } = useTableSort<RowSortKey>("spy", false);
  const {
    sortKey: altSortKey,
    sortAsc: altSortAsc,
    toggleSort: toggleAltSort,
  } = useTableSort<AltSortKey>("events", false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (kind) params.set("kind", kind);
    params.set("rollup", rollup ? "true" : "false");
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    try {
      const res = await fetch(`/api/audit/roster/interactions?${params}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setData(null);
        setError("Unable to load interaction audit.");
        return;
      }
      setData((await res.json()) as InteractionResponse);
    } catch {
      setData(null);
      setError("Unable to load interaction audit.");
    } finally {
      setLoading(false);
    }
  }, [q, kind, rollup, offset]);

  const loadDetail = useCallback(async (counterpartyId: number) => {
    const params = new URLSearchParams({
      counterparty_id: String(counterpartyId),
      rollup: "true",
      limit: "1",
    });
    try {
      const res = await fetch(`/api/audit/roster/interactions?${params}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (res.ok) setDetail((await res.json()) as InteractionResponse);
    } catch {
      setDetail(null);
    }
  }, []);


  const loadSpy = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/audit/roster/spy-meter?min_score=${minScore}&limit=100`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setSpyData(null);
        setError("Unable to load spy-o-meter.");
        return;
      }
      setSpyData((await res.json()) as SpyMeterResponse);
    } catch {
      setSpyData(null);
      setError("Unable to load spy-o-meter.");
    } finally {
      setLoading(false);
    }
  }, [minScore]);

  const rebuild = useCallback(async () => {
    setRebuilding(true);
    try {
      const res = await fetch("/api/audit/roster/rebuild-interactions", {
        method: "POST",
        credentials: "same-origin",
      });
      if (res.ok) {
        const body = (await res.json()) as { status?: string };
        if (body.status === "queued") {
          window.setTimeout(() => {
            void load();
            void loadSpy();
          }, 5000);
          return;
        }
      }
      await load();
      await loadSpy();
    } finally {
      setRebuilding(false);
    }
  }, [load, loadSpy]);

  useEffect(() => {
    if (tab === "spy-meter") {
      void loadSpy();
      return;
    }
    const t = window.setTimeout(() => void load(), q ? 280 : 0);
    return () => window.clearTimeout(t);
  }, [load, loadSpy, q, tab]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    setOffset(0);
  }, [q, kind, rollup]);


  const totalEvents = useMemo(
    () => (data?.rows ?? []).reduce((n, r) => n + r.event_count, 0),
    [data?.rows]
  );

  const highRiskCount = useMemo(
    () => (data?.rows ?? []).filter((r) => (r.spy_score ?? 0) >= 55).length,
    [data?.rows]
  );

  const channelBreakdown = useMemo(() => {
    const rows = detail?.by_character ?? [];
    if (!rows.length) return [];
    const map = new Map<string, number>();
    for (const row of rows) {
      map.set(row.channel, (map.get(row.channel) ?? 0) + row.event_count);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [detail?.by_character]);

  const selectedRow = useMemo(() => {
    if (selectedId == null) return null;
    const d = detail?.detail as
      | (InteractionRow & { entity_id?: number; entity_name?: string; entity_kind?: string })
      | undefined;
    if (d && (d.entity_id === selectedId || d.counterparty_id === selectedId)) {
      return {
        ...d,
        counterparty_id: d.entity_id ?? d.counterparty_id ?? selectedId,
        counterparty_name: d.entity_name ?? d.counterparty_name,
        counterparty_kind: d.entity_kind ?? d.counterparty_kind,
      } as InteractionRow;
    }
    const fromList = data?.rows.find((r) => r.counterparty_id === selectedId);
    if (fromList) return fromList;
    const fromSpy = spyData?.rows.find((r) => r.entity_id === selectedId);
    if (fromSpy) {
      return {
        counterparty_id: fromSpy.entity_id,
        counterparty_kind: fromSpy.entity_kind,
        counterparty_name: fromSpy.entity_name,
        channel: null,
        event_count: fromSpy.event_count,
        total_amount_isk: String(fromSpy.wallet_isk ?? 0),
        first_seen_at: null,
        last_seen_at: null,
        last_detail: "",
        alt_count: fromSpy.alt_count ?? 0,
        spy_score: fromSpy.spy_score,
        recommendation: fromSpy.recommendation,
        recommendation_label: fromSpy.recommendation_label,
        signals: fromSpy.signals,
        tags: fromSpy.tags,
        channels: fromSpy.channels,
        blacklisted: fromSpy.blacklisted,
        public_links: fromSpy.public_links,
      } as InteractionRow;
    }
    return null;
  }, [data, detail, selectedId, spyData]);


  const sortedRows = useMemo(
    () =>
      sortByKey(data?.rows ?? [], sortKey, sortAsc, (row, key) => {
        if (key === "counterparty") return row.counterparty_name;
        if (key === "kind") return row.counterparty_kind;
        if (key === "channel") return CHANNEL_LABELS[row.channel ?? ""] ?? row.channel ?? "";
        if (key === "events") return row.event_count;
        if (key === "alts") return row.alt_count;
        if (key === "spy") return row.spy_score ?? 0;
        return Date.parse(row.last_seen_at || "") || 0;
      }),
    [data?.rows, sortKey, sortAsc]
  );

  const sortedByCharacter = useMemo(
    () =>
      sortByKey(detail?.by_character ?? [], altSortKey, altSortAsc, (row, key) => {
        if (key === "pilot") return row.character_name;
        if (key === "channel") return CHANNEL_LABELS[row.channel] ?? row.channel;
        return row.event_count;
      }),
    [detail?.by_character, altSortKey, altSortAsc]
  );


  const applyTag = async () => {
    if (!selectedRow) return;
    setTagBusy(true);
    setTagMsg("");
    try {
      const res = await fetch("/api/audit/intel/tags", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_id: selectedRow.counterparty_id,
          entity_kind: selectedRow.counterparty_kind,
          entity_name: selectedRow.counterparty_name,
          tag_type: tagType,
          linked_character_id: linkCharId ? parseInt(linkCharId, 10) : null,
          linked_character_name: linkCharName,
          notes: tagNotes,
        }),
      });
      if (!res.ok) {
        setTagMsg("Failed to save tag.");
        return;
      }
      setTagMsg("Tag saved — spy-o-meter updated.");
      setTagNotes("");
      await load();
      await loadSpy();
      if (selectedId != null) await loadDetail(selectedId);

    } finally {
      setTagBusy(false);
    }
  };

  const removeTag = async (tagId: number) => {
    await fetch(`/api/audit/intel/tags/${tagId}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    await load();
    await loadSpy();
    if (selectedId != null) await loadDetail(selectedId);
  };


  const rowHeaders = useMemo(
    () => [
      {
        label: (
          <CharSheetSortButton
            label="Spy"
            active={sortKey === "spy"}
            asc={sortAsc}
            onClick={() => toggleSort("spy")}
          />
        ),
      },
      {
        label: (
          <CharSheetSortButton
            label="Counterparty"
            active={sortKey === "counterparty"}
            asc={sortAsc}
            onClick={() => toggleSort("counterparty")}
          />
        ),
      },
      {
        label: (
          <CharSheetSortButton
            label="Type"
            active={sortKey === "kind"}
            asc={sortAsc}
            onClick={() => toggleSort("kind")}
          />
        ),
      },
      ...(rollup
        ? []
        : [
            {
              label: (
                <CharSheetSortButton
                  label="Channel"
                  active={sortKey === "channel"}
                  asc={sortAsc}
                  onClick={() => toggleSort("channel")}
                />
              ),
            },
          ]),
      {
        label: (
          <CharSheetSortButton
            label="Events"
            active={sortKey === "events"}
            asc={sortAsc}
            onClick={() => toggleSort("events")}
          />
        ),
      },
      {
        label: (
          <CharSheetSortButton
            label="Alts"
            active={sortKey === "alts"}
            asc={sortAsc}
            onClick={() => toggleSort("alts")}
          />
        ),
      },
      {
        label: (
          <CharSheetSortButton
            label="Last seen"
            active={sortKey === "last_seen"}
            asc={sortAsc}
            onClick={() => toggleSort("last_seen")}
          />
        ),
      },
    ],
    [rollup, sortAsc, sortKey, toggleSort]
  );

  const renderDetail = () => {
    if (!selectedId || !selectedRow) {
      return (
        <p className="text-[10px] text-[var(--text-muted)]">
          Select a counterparty to tag as spy alt, review signals, and open public intel.
        </p>
      );
    }
    const links = selectedRow.public_links || {};
    return (
      <div className="space-y-2 text-[10px]">
        <p>
          <strong>{selectedRow.counterparty_name}</strong> · {selectedRow.event_count} events ·{" "}
          {selectedRow.alt_count} alt(s)
        </p>
        <div className="flex items-center gap-2">
          {scoreBar(selectedRow.spy_score ?? 0)}
          <span className={scoreTone(selectedRow.spy_score ?? 0)}>
            {selectedRow.recommendation_label || "—"}
          </span>
        </div>
        {selectedRow.blacklisted ? (
          <p className="text-[var(--danger)] font-semibold">On HR blacklist</p>
        ) : null}
        {Number(selectedRow.total_amount_isk) !== 0 ? (
          <p className="text-[var(--text-muted)]">
            Wallet volume: {fmtIskCompact(selectedRow.total_amount_isk)} ISK
          </p>
        ) : null}
        {selectedRow.last_detail ? (
          <p className="text-[var(--text-dim)] break-words">{selectedRow.last_detail}</p>
        ) : null}

        {selectedRow.channels && Object.keys(selectedRow.channels).length ? (
          <>
            <SectionHead>Channels</SectionHead>
            <ul className="space-y-0.5">
              {Object.entries(selectedRow.channels)
                .sort((a, b) => b[1] - a[1])
                .map(([ch, count]) => (
                  <li key={ch} className="flex justify-between">
                    <span
                      className={clsx(
                        ch === "combat_fleet" && "text-[var(--danger)] font-semibold",
                        (ch === "wallet" || ch === "contract") && "text-[var(--warn)]"
                      )}
                    >
                      {CHANNEL_LABELS[ch] ?? ch}
                    </span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
            </ul>
          </>
        ) : channelBreakdown.length ? (
          <>
            <SectionHead>By channel</SectionHead>
            <ul className="space-y-1">
              {channelBreakdown.map(([ch, count]) => (
                <li key={ch} className="flex justify-between">
                  <span>{CHANNEL_LABELS[ch] ?? ch}</span>
                  <span className="font-mono">{count}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {selectedRow.signals?.length ? (
          <>
            <SectionHead>Spy-o-meter signals</SectionHead>
            <ul className="space-y-1">
              {selectedRow.signals.map((s) => (
                <li key={s.key} className="flex justify-between gap-2">
                  <span>
                    {s.label}
                    {s.detail ? (
                      <span className="text-[var(--text-muted)]"> — {s.detail}</span>
                    ) : null}
                  </span>
                  <span className="font-mono text-[var(--warn)]">+{s.points}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {selectedRow.tags?.length ? (
          <>
            <SectionHead>Tags</SectionHead>
            <ul className="space-y-1">
              {selectedRow.tags.map((t) => (
                <li key={t.id} className="flex justify-between items-center gap-1">
                  <span>
                    <span
                      className={clsx(
                        t.tone === "danger" && "text-[var(--danger)]",
                        t.tone === "ok" && "text-[var(--ok)]",
                        t.tone === "warn" && "text-[var(--warn)]"
                      )}
                    >
                      {t.label}
                    </span>
                    {t.linked_character_name ? (
                      <span className="text-[var(--text-muted)]"> → {t.linked_character_name}</span>
                    ) : null}
                  </span>
                  <button type="button" className="eve-btn-sm text-[9px]" onClick={() => void removeTag(t.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        <SectionHead>Tie / tag entity</SectionHead>
        <div className="space-y-1.5">
          <select className="eve-select w-full" value={tagType} onChange={(e) => setTagType(e.target.value)}>
            {TAG_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <input
            className="eve-input w-full"
            placeholder="Linked character ID (alt of…)"
            value={linkCharId}
            onChange={(e) => setLinkCharId(e.target.value)}
          />
          <input
            className="eve-input w-full"
            placeholder="Linked character name"
            value={linkCharName}
            onChange={(e) => setLinkCharName(e.target.value)}
          />
          <input
            className="eve-input w-full"
            placeholder="Notes"
            value={tagNotes}
            onChange={(e) => setTagNotes(e.target.value)}
          />
          <button
            type="button"
            className="eve-btn-sm eve-btn-primary w-full"
            disabled={tagBusy}
            onClick={() => void applyTag()}
          >
            {tagBusy ? "Saving…" : "Save tag"}
          </button>
          {tagMsg ? <p className="text-[var(--ok)]">{tagMsg}</p> : null}
        </div>

        <SectionHead>Public intel</SectionHead>
        <div className="flex flex-wrap gap-2">
          {links.evewho ? (
            <a className="eve-btn-sm" href={links.evewho} target="_blank" rel="noreferrer">
              EveWho
            </a>
          ) : null}
          {links.zkill ? (
            <a className="eve-btn-sm" href={links.zkill} target="_blank" rel="noreferrer">
              zKill
            </a>
          ) : null}
          {links.eve411 ? (
            <a className="eve-btn-sm" href={links.eve411} target="_blank" rel="noreferrer">
              Eve411
            </a>
          ) : null}
        </div>

        {detail?.by_character.length ? (
          <>
            <SectionHead>Per alt</SectionHead>
            <table className="eve-table text-[9px] w-full">
              <thead>
                <tr>
                  <th>
                    <CharSheetSortButton
                      label="Pilot"
                      active={altSortKey === "pilot"}
                      asc={altSortAsc}
                      onClick={() => toggleAltSort("pilot")}
                    />
                  </th>
                  <th>
                    <CharSheetSortButton
                      label="Ch."
                      active={altSortKey === "channel"}
                      asc={altSortAsc}
                      onClick={() => toggleAltSort("channel")}
                    />
                  </th>
                  <th>
                    <CharSheetSortButton
                      label="#"
                      active={altSortKey === "events"}
                      asc={altSortAsc}
                      onClick={() => toggleAltSort("events")}
                    />
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedByCharacter.map((row) => (
                  <tr key={`${row.character_id}-${row.channel}`}>
                    <td className="truncate max-w-[100px]" title={row.character_name}>
                      {row.character_name}
                    </td>
                    <td
                      className={clsx(
                        row.channel === "combat_fleet" && "text-[var(--danger)] font-semibold"
                      )}
                    >
                      {CHANNEL_LABELS[row.channel] ?? row.channel}
                    </td>
                    <td className="font-mono">{row.event_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}

        <button type="button" className="eve-btn-sm" onClick={() => setSelectedId(null)}>
          Clear selection
        </button>
      </div>
    );
  };

  return (
    <div className="eve-interaction-audit text-[11px]">
      <StatusStrip>
        Fleet co-attackers, wallet/contracts, blacklist, standings, and manual tags feed the spy-o-meter
      </StatusStrip>

      <div className="flex flex-wrap gap-2 items-end mb-2 mt-2">
        <div className="flex gap-1">
          <button
            type="button"
            className={clsx("eve-btn-sm", tab === "interactions" && "eve-btn-primary")}
            onClick={() => setTab("interactions")}
          >
            Interactions
          </button>
          <button
            type="button"
            className={clsx("eve-btn-sm", tab === "spy-meter" && "eve-btn-primary")}
            onClick={() => setTab("spy-meter")}
          >
            Spy-o-meter
          </button>
        </div>
        {tab === "interactions" ? (
          <>
            <div className="flex-1 min-w-[160px]">
              <label className="text-[10px] text-[var(--text-muted)] block mb-1">Search</label>
              <input
                type="search"
                className="eve-input w-full"
                placeholder="Name, mail, wallet…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] text-[var(--text-muted)] block mb-1">Type</label>
              <select className="eve-select" value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => (
                  <option key={k.value || "all"} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-1 text-[10px] pb-1">
              <input type="checkbox" checked={rollup} onChange={(e) => setRollup(e.target.checked)} />
              Roll up channels
            </label>
          </>
        ) : (
          <div>
            <label className="text-[10px] text-[var(--text-muted)] block mb-1">Min score</label>
            <select
              className="eve-select"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            >
              <option value={0}>All</option>
              <option value={30}>Watch+</option>
              <option value={55}>Suspicious+</option>
              <option value={80}>Likely alt</option>
            </select>
          </div>
        )}
        <button
          type="button"
          className="eve-btn-sm"
          disabled={loading}
          onClick={() => void (tab === "spy-meter" ? loadSpy() : load())}
        >
          Refresh
        </button>
        <button
          type="button"
          className="eve-btn-sm eve-btn-primary"
          disabled={rebuilding}
          onClick={() => void rebuild()}
        >
          {rebuilding ? "Rebuilding…" : "Rebuild from DB"}
        </button>
      </div>

      <KpiStrip>
        {tab === "interactions" ? (
          <>
            <KpiTile label="Counterparties" value={String(data?.total ?? "—")} tone="accent" />
            <KpiTile label="Events (page)" value={loading ? "…" : String(totalEvents)} />
            <KpiTile label="High risk (page)" value={String(highRiskCount)} tone="warn" />
          </>
        ) : (
          <>
            <KpiTile label="Ranked" value={String(spyData?.total ?? "—")} tone="warn" />
            <KpiTile
              label="Likely alts"
              value={String((spyData?.rows ?? []).filter((r) => r.spy_score >= 80).length)}
              tone="danger"
            />
            <KpiTile
              label="Suspicious"
              value={String(
                (spyData?.rows ?? []).filter((r) => r.spy_score >= 55 && r.spy_score < 80).length
              )}
            />
          </>
        )}
      </KpiStrip>

      {error ? <p className="text-[var(--danger)] mt-2">{error}</p> : null}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3 mt-2">
        <div>
          {tab === "interactions" ? (
            <>
              <p className="text-[10px] text-[var(--text-muted)] mb-1">
                Fleet = co-attacker on same zKill · Wallet/contracts with holding corps are high signal ·
                click a row to tag as spy alt
              </p>
              <EveTable headers={rowHeaders}>
                {sortedRows.map((row) => (
                  <tr
                    key={`${row.counterparty_id}-${row.channel ?? "all"}`}
                    className={clsx(
                      "cursor-pointer",
                      selectedId === row.counterparty_id && "bg-[var(--surface-raised)]",
                      (row.spy_score ?? 0) >= 80 && "bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]"
                    )}
                    onClick={() => setSelectedId(row.counterparty_id)}
                  >
                    <td>{scoreBar(row.spy_score ?? 0)}</td>
                    <td>
                      <div className="font-medium flex items-center gap-1 flex-wrap">
                        {row.counterparty_name}
                        {row.blacklisted ? (
                          <span className="text-[9px] text-[var(--danger)]">BL</span>
                        ) : null}
                        {row.tags?.map((t) => (
                          <span
                            key={t.id}
                            className={clsx(
                              "text-[9px]",
                              t.tone === "danger" && "text-[var(--danger)]",
                              t.tone === "warn" && "text-[var(--warn)]",
                              t.tone === "ok" && "text-[var(--ok)]"
                            )}
                          >
                            [{t.label}]
                          </span>
                        ))}
                      </div>
                      <div className="text-[9px] text-[var(--text-dim)] font-mono">
                        {row.counterparty_id}
                        {row.channels?.combat_fleet ? (
                          <span className="text-[var(--danger)] ml-1">
                            · fleet×{row.channels.combat_fleet}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>{kindBadge(row.counterparty_kind)}</td>
                    {!rollup ? (
                      <td
                        className={clsx(
                          "text-[10px]",
                          row.channel === "combat_fleet" && "text-[var(--danger)] font-semibold"
                        )}
                      >
                        {CHANNEL_LABELS[row.channel ?? ""] ?? row.channel}
                      </td>
                    ) : null}
                    <td className="font-mono">{row.event_count.toLocaleString()}</td>
                    <td>{row.alt_count}</td>
                    <td className="text-[10px] text-[var(--text-muted)]">{fmtWhen(row.last_seen_at)}</td>
                  </tr>
                ))}
              </EveTable>
              {!loading && !data?.rows.length ? (
                <p className="text-[var(--text-muted)] p-2">
                  No interactions yet. Sync character audits or run Rebuild from DB.
                </p>
              ) : null}
              {data && data.total > limit ? (
                <div className="flex gap-2 mt-2 justify-end">
                  <button
                    type="button"
                    className="eve-btn-sm"
                    disabled={offset <= 0}
                    onClick={() => setOffset((o) => Math.max(0, o - limit))}
                  >
                    Previous
                  </button>
                  <span className="text-[10px] text-[var(--text-muted)] self-center">
                    {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
                  </span>
                  <button
                    type="button"
                    className="eve-btn-sm"
                    disabled={offset + limit >= data.total}
                    onClick={() => setOffset((o) => o + limit)}
                  >
                    Next
                  </button>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <p className="text-[10px] text-[var(--text-muted)] mb-1">
                Ranked by fleet activity, trades/contracts, blacklist, standings, HR flags, and your tags
              </p>
              <EveTable
                headers={[
                  { label: "Spy" },
                  { label: "Entity" },
                  { label: "Verdict" },
                  { label: "Events" },
                  { label: "Top signals" },
                ]}
              >
                {(spyData?.rows ?? []).map((row) => (
                  <tr
                    key={row.entity_id}
                    className={clsx(
                      "cursor-pointer",
                      selectedId === row.entity_id && "bg-[var(--surface-raised)]",
                      row.spy_score >= 80 && "bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]"
                    )}
                    onClick={() => setSelectedId(row.entity_id)}
                  >
                    <td>{scoreBar(row.spy_score)}</td>
                    <td>
                      <div className="font-medium">{row.entity_name}</div>
                      <div className="text-[9px] text-[var(--text-dim)]">
                        {kindBadge(row.entity_kind)} · {row.entity_id}
                      </div>
                    </td>
                    <td className={scoreTone(row.spy_score)}>{row.recommendation_label}</td>
                    <td className="font-mono">{row.event_count}</td>
                    <td className="text-[9px] text-[var(--text-muted)] max-w-[200px] truncate">
                      {(row.signals ?? [])
                        .slice(0, 3)
                        .map((s) => s.label)
                        .join(" · ")}
                    </td>
                  </tr>
                ))}
              </EveTable>
              {!loading && !spyData?.rows.length ? (
                <p className="text-[var(--text-muted)] p-2">
                  No entities at this score threshold. Rebuild interactions after audit sync, or lower min
                  score.
                </p>
              ) : null}
            </>
          )}
        </div>

        <div className="border border-[var(--border)] p-2 min-h-[120px]">{renderDetail()}</div>
      </div>
    </div>
  );
}
