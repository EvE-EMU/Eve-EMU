"use client";

import { useCallback, useEffect, useState } from "react";
import { EveWindow } from "@/components/ui";
import { DesktopSurface } from "@/components/WindowManager";
import { SectionHead, StatusStrip } from "@/components/ui";
import { useWindowManagerOptional } from "@/components/WindowManager";

type CatalogTool = {
  category: string;
  sources: string[];
  window_id: string;
  label: string;
  description: string;
};

function fmtIsk(n: number) {
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function AwesomeSuiteWorkspace({ embedded }: { embedded?: boolean }) {
  const wm = useWindowManagerOptional();
  const [catalog, setCatalog] = useState<CatalogTool[]>([]);
  const [catalogNote, setCatalogNote] = useState("");

  useEffect(() => {
    fetch("/api/tools/suite/catalog", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setCatalog(data.tools || []);
        setCatalogNote(data.note || "");
      })
      .catch(() => undefined);
  }, []);

  const open = useCallback(
    (windowId: string) => {
      if (!wm) return;
      wm.openWindow(windowId);
      wm.focusWindow(windowId);
    },
    [wm]
  );

  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <EveWindow
        id="suite-hub"
        title="Awesome EVE Tool Suite"
        defaultX={24}
        defaultY={24}
        defaultWidth={720}
        defaultHeight={520}
      >
        <StatusStrip>
          Combined from{" "}
          <a
            href="https://github.com/devfleet/awesome-eve"
            target="_blank"
            rel="noreferrer"
            className="eve-char-sheet-link"
          >
            awesome-eve
          </a>{" "}
          — live ESI / zKill / market / audit data only
        </StatusStrip>
        {catalogNote ? <p className="text-[11px] text-[var(--text-muted)] mb-2">{catalogNote}</p> : null}
        <div className="grid gap-2 sm:grid-cols-2">
          {catalog.map((t) => (
            <button
              key={t.window_id + t.label}
              type="button"
              className="eve-panel text-left p-2 hover:border-[var(--accent)]"
              onClick={() => open(t.window_id)}
            >
              <div className="text-[10px] uppercase text-[var(--text-muted)]">{t.category}</div>
              <div className="font-semibold text-sm">{t.label}</div>
              <div className="text-[11px] text-[var(--text-muted)] mt-1">{t.description}</div>
              <div className="text-[10px] text-[var(--text-dim)] mt-1">
                Inspired by: {t.sources.join(", ")}
              </div>
            </button>
          ))}
        </div>
      </EveWindow>

      <IntelPasteWindow />
      <TradeMarginsWindow />
      <CorpWhoWindow />
      <BattleReportWindow />
      <SkillQueuesWindow />
      <GateCampRouteWindow />
      <HaulFinderWindow />
      <StructureBoardWindow />
      <ShipCompareWindow />
      <InsuranceCheckWindow />
    </DesktopSurface>
  );
}

function IntelPasteWindow() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    summary?: { characters: number; types: number; systems: number; unknown: number };
    characters?: {
      name: string;
      id: number;
      corporation_name?: string;
      alliance_name?: string;
      zkill?: { ships_destroyed: number; ships_lost: number; url: string } | null;
    }[];
    types?: { name: string; id: number }[];
    corp_breakdown?: { name: string; count: number }[];
  } | null>(null);

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/tools/suite/intel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, with_zkill: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Intel lookup failed");
        setResult(null);
        return;
      }
      setResult(data);
    } catch {
      setError("Intel lookup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-intel" title="Intel Paste" defaultX={48} defaultY={48} defaultWidth={780} defaultHeight={560}>
      <StatusStrip>Paste local chat, D-scan, or pilot lists — ESI resolve + zKill (PySpy / Eve411 / Eve Squadron)</StatusStrip>
      <textarea
        className="eve-input w-full h-28 font-mono text-[11px]"
        placeholder="Paste names or D-scan lines…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex gap-2 my-2">
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading || !text.trim()}>
          {loading ? "Resolving…" : "Resolve"}
        </button>
        {error ? <span className="text-[var(--danger)] text-sm">{error}</span> : null}
      </div>
      {result?.summary ? (
        <div className="text-[11px] mb-2">
          Characters {result.summary.characters} · Types {result.summary.types} · Systems{" "}
          {result.summary.systems} · Unknown {result.summary.unknown}
        </div>
      ) : null}
      {result?.corp_breakdown?.length ? (
        <>
          <SectionHead>Corps in local</SectionHead>
          <ul className="text-[11px] mb-2 columns-2">
            {result.corp_breakdown.map((c) => (
              <li key={c.name}>
                {c.name}: {c.count}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {result?.characters?.length ? (
        <div className="overflow-auto max-h-64">
          <table className="eve-table w-full text-[11px]">
            <thead>
              <tr>
                <th>Pilot</th>
                <th>Corp</th>
                <th>Alliance</th>
                <th>Kills</th>
                <th>Losses</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {result.characters.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.corporation_name || "—"}</td>
                  <td>{c.alliance_name || "—"}</td>
                  <td>{c.zkill?.ships_destroyed ?? "—"}</td>
                  <td>{c.zkill?.ships_lost ?? "—"}</td>
                  <td>
                    {c.zkill?.url ? (
                      <a href={c.zkill.url} target="_blank" rel="noreferrer" className="eve-char-sheet-link">
                        zKill
                      </a>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {result?.types?.length ? (
        <>
          <SectionHead>D-scan types</SectionHead>
          <ul className="text-[11px] columns-2">
            {result.types.map((t) => (
              <li key={t.id}>
                {t.name} <span className="text-[var(--text-muted)]">({t.id})</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </EveWindow>
  );
}

function TradeMarginsWindow() {
  const [text, setText] = useState("");
  const [hub, setHub] = useState("jita");
  const [loading, setLoading] = useState(false);
  const [lines, setLines] = useState<
    { type_id: number; name: string; buy: number; sell: number; spread: number; margin_pct: number }[]
  >([]);
  const [source, setSource] = useState("");

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tools/suite/trade-margins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, hub, limit: 40 }),
      });
      const data = await res.json();
      setLines(data.lines || []);
      setSource(data.pricing_source || "");
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-trade" title="Trade Margins" defaultX={72} defaultY={72} defaultWidth={760} defaultHeight={520}>
      <StatusStrip>Hub spreads from live market data (EVE Trade / EveMarketTool / Priceall)</StatusStrip>
      <div className="flex flex-wrap gap-2 items-end mb-2 text-[11px]">
        <label>
          Hub
          <select className="eve-select ml-1" value={hub} onChange={(e) => setHub(e.target.value)}>
            <option value="jita">Jita</option>
            <option value="amarr">Amarr</option>
            <option value="dodixie">Dodixie</option>
            <option value="rens">Rens</option>
            <option value="hek">Hek</option>
          </select>
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Pricing…" : "Scan margins"}
        </button>
        {source ? <span className="text-[var(--text-muted)]">Source: {source}</span> : null}
      </div>
      <textarea
        className="eve-input w-full h-20 font-mono text-[11px] mb-2"
        placeholder="Optional: paste item names (blank = sample from SDE index)"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Item</th>
              <th className="text-end">Buy</th>
              <th className="text-end">Sell</th>
              <th className="text-end">Spread</th>
              <th className="text-end">Margin %</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((r) => (
              <tr key={r.type_id}>
                <td>{r.name}</td>
                <td className="text-end">{fmtIsk(r.buy)}</td>
                <td className="text-end">{fmtIsk(r.sell)}</td>
                <td className="text-end">{fmtIsk(r.spread)}</td>
                <td className="text-end">{r.margin_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function CorpWhoWindow() {
  const [name, setName] = useState("False Gods");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    corporation_name?: string;
    ticker?: string;
    member_count?: number;
    members?: { character_id: number; character_name: string; zkill_url: string }[];
    note?: string;
    error?: string;
  } | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/tools/suite/corp-who?corporation_name=${encodeURIComponent(name.trim())}`,
        { cache: "no-store" }
      );
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-corpwho" title="Corp Who" defaultX={96} defaultY={96} defaultWidth={640} defaultHeight={520}>
      <StatusStrip>Live corp roster via ESI (EveWho / SeAT style)</StatusStrip>
      <div className="flex gap-2 mb-2">
        <input
          className="eve-input flex-1"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Corporation name"
        />
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Loading…" : "Lookup"}
        </button>
      </div>
      {data?.error ? <p className="text-[var(--danger)] text-sm">{data.error}</p> : null}
      {data?.corporation_name ? (
        <div className="text-[12px] mb-2">
          <strong>{data.corporation_name}</strong> [{data.ticker}] — {data.member_count} members
        </div>
      ) : null}
      {data?.note ? <p className="text-[11px] text-[var(--warn)] mb-2">{data.note}</p> : null}
      {data?.members?.length ? (
        <div className="overflow-auto max-h-80">
          <ul className="text-[11px] columns-2">
            {data.members.map((m) => (
              <li key={m.character_id}>
                {m.character_name}{" "}
                <a href={m.zkill_url} target="_blank" rel="noreferrer" className="eve-char-sheet-link">
                  zKill
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </EveWindow>
  );
}

function BattleReportWindow() {
  const [systemId, setSystemId] = useState("30000142");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    kill_count?: number;
    total_isk?: number;
    kills?: { killmail_id: number; total_value: number; zkill_url: string; killmail_time?: string }[];
  } | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/tools/suite/battle-report?system_id=${encodeURIComponent(systemId)}&limit=40`,
        { cache: "no-store" }
      );
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-br" title="Battle Report" defaultX={120} defaultY={120} defaultWidth={640} defaultHeight={480}>
      <StatusStrip>System kill aggregation from zKill (brcat-style)</StatusStrip>
      <div className="flex gap-2 mb-2 text-[11px]">
        <label>
          System ID
          <input className="eve-input w-28 ml-1" value={systemId} onChange={(e) => setSystemId(e.target.value)} />
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Loading…" : "Load"}
        </button>
      </div>
      {data ? (
        <div className="text-[12px] mb-2">
          Kills: {data.kill_count ?? 0} · ISK: {fmtIsk(data.total_isk || 0)}
        </div>
      ) : null}
      <div className="overflow-auto max-h-72">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Kill</th>
              <th>Time</th>
              <th className="text-end">Value</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data?.kills || []).map((k) => (
              <tr key={k.killmail_id}>
                <td>{k.killmail_id}</td>
                <td>{k.killmail_time || "—"}</td>
                <td className="text-end">{fmtIsk(k.total_value)}</td>
                <td>
                  <a href={k.zkill_url} target="_blank" rel="noreferrer" className="eve-char-sheet-link">
                    zKill
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function SkillQueuesWindow() {
  const [loading, setLoading] = useState(false);
  const [chars, setChars] = useState<
    { character_id: number; character_name: string; skill_count: number; total_sp: number }[]
  >([]);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/tools/suite/skill-queues", { cache: "no-store" });
      if (!res.ok) {
        setError(res.status === 401 ? "Log in to view skill queues." : "Failed to load skills.");
        setChars([]);
        return;
      }
      const data = await res.json();
      setChars(data.characters || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void run();
  }, []);

  return (
    <EveWindow id="suite-skills" title="Skill Queues" defaultX={144} defaultY={144} defaultWidth={560} defaultHeight={420}>
      <StatusStrip>Roster skills from ESI audit DB (SkillQ / Cerebral)</StatusStrip>
      <button type="button" className="eve-btn eve-btn-secondary text-sm mb-2" onClick={() => void run()} disabled={loading}>
        {loading ? "Loading…" : "Refresh"}
      </button>
      {error ? <p className="text-[var(--danger)] text-sm">{error}</p> : null}
      <table className="eve-table w-full text-[11px]">
        <thead>
          <tr>
            <th>Character</th>
            <th className="text-end">Skills</th>
            <th className="text-end">Total SP</th>
          </tr>
        </thead>
        <tbody>
          {chars.map((c) => (
            <tr key={c.character_id}>
              <td>{c.character_name || c.character_id}</td>
              <td className="text-end">{c.skill_count}</td>
              <td className="text-end">{fmtIsk(c.total_sp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </EveWindow>
  );
}

function GateCampRouteWindow() {
  const [origin, setOrigin] = useState("30000142");
  const [dest, setDest] = useState("30002187");
  const [avoidLow, setAvoidLow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    jumps?: number;
    error?: string;
    message?: string;
    systems?: {
      system_id: number;
      name: string;
      security: number;
      heat: string;
      ships_destroyed: number;
      isk_destroyed: number;
      zkill_url: string;
    }[];
    hot_systems?: { name: string; heat: string }[];
  } | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tools/suite/gate-camp-route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin_system_id: Number(origin),
          destination_system_id: Number(dest),
          avoid_low_sec: avoidLow,
        }),
      });
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-gatecamp" title="Gate Camp Route" defaultX={40} defaultY={40} defaultWidth={720} defaultHeight={520}>
      <StatusStrip>Route heat map from zKill (Gate Camp Check / Eden Navigator)</StatusStrip>
      <div className="flex flex-wrap gap-2 mb-2 text-[11px] items-end">
        <label>
          Origin system ID
          <input className="eve-input w-28 ml-1" value={origin} onChange={(e) => setOrigin(e.target.value)} />
        </label>
        <label>
          Destination system ID
          <input className="eve-input w-28 ml-1" value={dest} onChange={(e) => setDest(e.target.value)} />
        </label>
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={avoidLow} onChange={(e) => setAvoidLow(e.target.checked)} />
          Avoid low/null
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Routing…" : "Plan route"}
        </button>
      </div>
      {data?.error ? <p className="text-[var(--danger)] text-sm">{data.message || data.error}</p> : null}
      {data?.jumps != null ? (
        <div className="text-[12px] mb-2">
          Jumps: {data.jumps} · Hot/warm systems: {data.hot_systems?.length ?? 0}
        </div>
      ) : null}
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>System</th>
              <th>Sec</th>
              <th>Heat</th>
              <th className="text-end">Ships</th>
              <th className="text-end">ISK</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data?.systems || []).map((s) => (
              <tr key={s.system_id}>
                <td>{s.name}</td>
                <td>{Number(s.security).toFixed(1)}</td>
                <td className={s.heat === "hot" ? "text-[var(--danger)]" : s.heat === "warm" ? "text-[var(--warn)]" : ""}>
                  {s.heat}
                </td>
                <td className="text-end">{s.ships_destroyed}</td>
                <td className="text-end">{fmtIsk(s.isk_destroyed)}</td>
                <td>
                  <a href={s.zkill_url} target="_blank" rel="noreferrer" className="eve-char-sheet-link">
                    zKill
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function HaulFinderWindow() {
  const [buyHub, setBuyHub] = useState("jita");
  const [sellHub, setSellHub] = useState("amarr");
  const [minMargin, setMinMargin] = useState(5);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<
    { type_id: number; name: string; buy_price: number; sell_price: number; profit_per_unit: number; margin_pct: number }[]
  >([]);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tools/suite/haul-finder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          buy_hub: buyHub,
          sell_hub: sellHub,
          min_margin_pct: minMargin,
          text,
          limit: 30,
        }),
      });
      const data = await res.json();
      setRows(data.opportunities || []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-haul" title="Haul Finder" defaultX={64} defaultY={64} defaultWidth={760} defaultHeight={520}>
      <StatusStrip>Cross-hub haul margins (EVE Trade / Adam4EVE)</StatusStrip>
      <div className="flex flex-wrap gap-2 mb-2 text-[11px] items-end">
        <label>
          Buy hub
          <select className="eve-select ml-1" value={buyHub} onChange={(e) => setBuyHub(e.target.value)}>
            {["jita", "amarr", "dodixie", "rens", "hek"].map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </label>
        <label>
          Sell hub
          <select className="eve-select ml-1" value={sellHub} onChange={(e) => setSellHub(e.target.value)}>
            {["jita", "amarr", "dodixie", "rens", "hek"].map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </label>
        <label>
          Min margin %
          <input
            className="eve-input w-16 ml-1"
            type="number"
            value={minMargin}
            onChange={(e) => setMinMargin(Number(e.target.value) || 0)}
          />
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Scanning…" : "Find hauls"}
        </button>
      </div>
      <textarea
        className="eve-input w-full h-16 font-mono text-[11px] mb-2"
        placeholder="Optional item names (blank = SDE sample)"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Item</th>
              <th className="text-end">Buy</th>
              <th className="text-end">Sell</th>
              <th className="text-end">Profit/u</th>
              <th className="text-end">Margin %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.type_id}>
                <td>{r.name}</td>
                <td className="text-end">{fmtIsk(r.buy_price)}</td>
                <td className="text-end">{fmtIsk(r.sell_price)}</td>
                <td className="text-end">{fmtIsk(r.profit_per_unit)}</td>
                <td className="text-end">{r.margin_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function StructureBoardWindow() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    count?: number;
    with_market?: number;
    with_reprocessing?: number;
    structures?: {
      structure_id: number;
      structure_name: string;
      system_name: string;
      has_market: boolean;
      has_reprocessing: boolean;
    }[];
  } | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tools/suite/structure-board", { cache: "no-store" });
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void run();
  }, []);

  return (
    <EveWindow id="suite-structures" title="Structure Board" defaultX={88} defaultY={88} defaultWidth={720} defaultHeight={480}>
      <StatusStrip>Authed structures from ESI sync (Upwell / SeAT style)</StatusStrip>
      <button type="button" className="eve-btn eve-btn-secondary text-sm mb-2" onClick={() => void run()} disabled={loading}>
        {loading ? "Loading…" : "Refresh"}
      </button>
      {data ? (
        <div className="text-[12px] mb-2">
          {data.count} structures · market {data.with_market} · reprocessing {data.with_reprocessing}
        </div>
      ) : null}
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Structure</th>
              <th>System</th>
              <th>Market</th>
              <th>Reprocess</th>
            </tr>
          </thead>
          <tbody>
            {(data?.structures || []).map((s) => (
              <tr key={s.structure_id}>
                <td>{s.structure_name}</td>
                <td>{s.system_name || "—"}</td>
                <td>{s.has_market ? "yes" : "—"}</td>
                <td>{s.has_reprocessing ? "yes" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function ShipCompareWindow() {
  const [typeA, setTypeA] = useState("587");
  const [typeB, setTypeB] = useState("17738");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    error?: string;
    a?: { name: string; group_name?: string; mass?: number; volume_m3?: number };
    b?: { name: string; group_name?: string; mass?: number; volume_m3?: number };
    comparisons?: { attribute: string; a?: number; b?: number }[];
  } | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/tools/suite/ship-compare?type_a=${encodeURIComponent(typeA)}&type_b=${encodeURIComponent(typeB)}`,
        { cache: "no-store" }
      );
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-ships" title="Ship Compare" defaultX={112} defaultY={112} defaultWidth={720} defaultHeight={520}>
      <StatusStrip>Hull dogma compare (Pyfa / Theorycrafter lite)</StatusStrip>
      <div className="flex flex-wrap gap-2 mb-2 text-[11px] items-end">
        <label>
          Type A ID
          <input className="eve-input w-24 ml-1" value={typeA} onChange={(e) => setTypeA(e.target.value)} />
        </label>
        <label>
          Type B ID
          <input className="eve-input w-24 ml-1" value={typeB} onChange={(e) => setTypeB(e.target.value)} />
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Loading…" : "Compare"}
        </button>
      </div>
      {data?.error ? <p className="text-[var(--danger)] text-sm">{data.error}</p> : null}
      {data?.a && data?.b ? (
        <div className="text-[12px] mb-2 grid grid-cols-2 gap-2">
          <div>
            <strong>{data.a.name}</strong>
            <div className="text-[var(--text-muted)]">{data.a.group_name}</div>
          </div>
          <div>
            <strong>{data.b.name}</strong>
            <div className="text-[var(--text-muted)]">{data.b.group_name}</div>
          </div>
        </div>
      ) : null}
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Attribute</th>
              <th className="text-end">{data?.a?.name || "A"}</th>
              <th className="text-end">{data?.b?.name || "B"}</th>
            </tr>
          </thead>
          <tbody>
            {(data?.comparisons || []).map((c) => (
              <tr key={c.attribute}>
                <td>{c.attribute}</td>
                <td className="text-end">{c.a != null ? c.a.toLocaleString() : "—"}</td>
                <td className="text-end">{c.b != null ? c.b.toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}

function InsuranceCheckWindow() {
  const [text, setText] = useState("");
  const [hub, setHub] = useState("jita");
  const [loading, setLoading] = useState(false);
  const [lines, setLines] = useState<
    {
      type_id: number;
      name: string;
      platinum_payout: number;
      market_buy: number;
      fraud_profit: number;
      worth_insuring: boolean;
    }[]
  >([]);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tools/suite/insurance-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, hub }),
      });
      const data = await res.json();
      setLines(data.lines || []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <EveWindow id="suite-insurance" title="Insurance Check" defaultX={136} defaultY={136} defaultWidth={720} defaultHeight={480}>
      <StatusStrip>Platinum payout vs market buy (Eve Insurance Fraud style)</StatusStrip>
      <div className="flex flex-wrap gap-2 mb-2 text-[11px] items-end">
        <label>
          Hub
          <select className="eve-select ml-1" value={hub} onChange={(e) => setHub(e.target.value)}>
            {["jita", "amarr", "dodixie", "rens", "hek"].map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </label>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void run()} disabled={loading}>
          {loading ? "Checking…" : "Check hulls"}
        </button>
      </div>
      <textarea
        className="eve-input w-full h-16 font-mono text-[11px] mb-2"
        placeholder="Optional ship names (blank = top ships by base price)"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="overflow-auto max-h-80">
        <table className="eve-table w-full text-[11px]">
          <thead>
            <tr>
              <th>Ship</th>
              <th className="text-end">Platinum</th>
              <th className="text-end">Market buy</th>
              <th className="text-end">Profit</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((r) => (
              <tr key={r.type_id}>
                <td>{r.name}</td>
                <td className="text-end">{fmtIsk(r.platinum_payout)}</td>
                <td className="text-end">{fmtIsk(r.market_buy)}</td>
                <td className="text-end">{fmtIsk(r.fraud_profit)}</td>
                <td className={r.worth_insuring ? "text-[var(--warn)]" : ""}>
                  {r.worth_insuring ? "check" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EveWindow>
  );
}
