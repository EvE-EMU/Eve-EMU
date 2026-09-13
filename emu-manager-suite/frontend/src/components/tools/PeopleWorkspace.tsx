"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EveWindow, SectionHead, StatusStrip } from "@/components/ui";
import { DesktopSurface, useWindowManagerOptional } from "@/components/WindowManager";

function fmtIsk(n: number) {
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function PeopleWorkspace({ embedded }: { embedded?: boolean }) {
  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <EveWindow id="onboarding" title="Onboarding Manager" defaultX={24} defaultY={24} defaultWidth={560} defaultHeight={520}>
        <OnboardingPanel />
      </EveWindow>
      <EveWindow id="admission-rank" title="Admission Ranking" defaultX={600} defaultY={24} defaultWidth={520} defaultHeight={520}>
        <AdmissionRankPanel />
      </EveWindow>
      <EveWindow id="standings-sync" title="Standings Sync" defaultX={24} defaultY={560} defaultWidth={520} defaultHeight={400}>
        <StandingsPanel />
      </EveWindow>
      <EveWindow id="ops-calendar" title="Operations Calendar" defaultX={560} defaultY={560} defaultWidth={640} defaultHeight={480}>
        <CalendarPanel />
      </EveWindow>
    </DesktopSurface>
  );
}

function OnboardingPanel() {
  const wm = useWindowManagerOptional();
  const [data, setData] = useState<{
    tasks: {
      slug: string;
      title: string;
      description: string;
      points: number;
      completed: boolean;
      window_id: string;
      category: string;
    }[];
    progress_pct: number;
    points_earned: number;
    points_total: number;
    achievements: { slug: string; title: string; unlocked: boolean }[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/people/onboarding", { cache: "no-store" });
      if (!res.ok) {
        setError(res.status === 401 ? "Log in to start onboarding." : "Failed to load onboarding.");
        return;
      }
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const complete = async (slug: string, windowId?: string) => {
    if (windowId && wm) {
      wm.openWindow(windowId);
      wm.focusWindow(windowId);
    }
    const res = await fetch("/api/people/onboarding/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_slug: slug }),
    });
    if (res.ok) setData(await res.json());
  };

  if (!data) {
    return (
      <div className="p-2 text-[11px]">
        {loading ? "Loading…" : error || "No data"}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full text-[11px]">
      <StatusStrip>
        Progress {data.progress_pct}% · {data.points_earned}/{data.points_total} points
      </StatusStrip>
      <div className="h-2 bg-[var(--panel-inset)] border border-[var(--edge-dim)]">
        <div className="h-full bg-[var(--accent)]" style={{ width: `${data.progress_pct}%` }} />
      </div>
      <SectionHead>Achievements</SectionHead>
      <div className="flex flex-wrap gap-1">
        {data.achievements.map((a) => (
          <span
            key={a.slug}
            className={`eve-tag ${a.unlocked ? "text-[var(--ok)]" : "text-[var(--text-muted)] opacity-60"}`}
          >
            {a.unlocked ? "✓ " : ""}
            {a.title}
          </span>
        ))}
      </div>
      <SectionHead>Tasks</SectionHead>
      <ul className="space-y-2 overflow-auto min-h-0 flex-1">
        {data.tasks.map((t) => (
          <li key={t.slug} className="border border-[var(--edge-dim)] p-2">
            <div className="flex justify-between gap-2">
              <div>
                <strong className={t.completed ? "line-through text-[var(--text-muted)]" : ""}>
                  {t.title}
                </strong>
                <div className="text-[var(--text-muted)]">{t.description}</div>
                <div className="text-[9px] text-[var(--text-muted)]">
                  {t.category} · {t.points} pts
                </div>
              </div>
              {t.completed ? (
                <span className="text-[var(--ok)]">Done</span>
              ) : (
                <button
                  type="button"
                  className="eve-btn eve-btn-primary text-[10px] self-start"
                  onClick={() => void complete(t.slug, t.window_id)}
                >
                  {t.window_id ? "Open & complete" : "Mark done"}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AdmissionRankPanel() {
  const [rank, setRank] = useState<{
    score: number;
    recommendation: string;
    recommendation_label: string;
    admit_threshold: number;
    review_threshold: number;
    breakdown: { label: string; score: number; raw_value: number; weight: number; target_value: number }[];
    character_name: string;
  } | null>(null);
  const [config, setConfig] = useState<{
    admit_threshold: number;
    review_threshold: number;
    kpis: { id: number; label: string; weight: number; active: boolean; target_value: number }[];
  } | null>(null);
  const [lookupId, setLookupId] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const loadMe = useCallback(async () => {
    setError("");
    const res = await fetch("/api/people/admission/rank", { cache: "no-store" });
    if (!res.ok) {
      setError(res.status === 401 ? "Log in to view ranking." : "Failed to load rank.");
      return;
    }
    setRank(await res.json());
  }, []);

  const loadConfig = useCallback(async () => {
    const res = await fetch("/api/people/admission/config", { cache: "no-store" });
    if (res.ok) setConfig(await res.json());
  }, []);

  useEffect(() => {
    void loadMe();
    void loadConfig();
  }, [loadMe, loadConfig]);

  const lookup = async () => {
    const id = parseInt(lookupId, 10);
    if (!id) return;
    setError("");
    const res = await fetch(`/api/people/admission/rank/${id}`, { cache: "no-store" });
    if (!res.ok) {
      setError(res.status === 403 ? "Director access required for applicant lookup." : "Lookup failed.");
      return;
    }
    setRank(await res.json());
  };

  const saveConfig = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await fetch("/api/people/admission/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          admit_threshold: config.admit_threshold,
          review_threshold: config.review_threshold,
          kpi_updates: config.kpis.map((k) => ({
            id: k.id,
            weight: k.weight,
            active: k.active,
            target_value: k.target_value,
          })),
        }),
      });
      if (res.ok) setConfig(await res.json());
    } finally {
      setSaving(false);
    }
  };

  const recClass =
    rank?.recommendation === "admit"
      ? "text-[var(--ok)]"
      : rank?.recommendation === "review"
        ? "text-[var(--warn)]"
        : "text-[var(--danger)]";

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full text-[11px]">
      <StatusStrip>Configurable KPI score for corp admission decisions</StatusStrip>
      <div className="flex gap-2">
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => void loadMe()}>
          Score me
        </button>
        <input
          className="eve-input w-28"
          placeholder="Character ID"
          value={lookupId}
          onChange={(e) => setLookupId(e.target.value)}
        />
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void lookup()}>
          Score applicant
        </button>
      </div>
      {error ? <p className="text-[var(--danger)]">{error}</p> : null}
      {rank ? (
        <div className="border border-[var(--edge-dim)] p-2">
          <div className="text-[14px] font-semibold">
            {rank.character_name || rank.score} — <span className={recClass}>{rank.recommendation_label}</span>
          </div>
          <div className="text-[20px] font-bold tabular-nums">{rank.score.toFixed(1)}</div>
          <div className="text-[var(--text-muted)] text-[10px]">
            Admit ≥ {rank.admit_threshold} · Review ≥ {rank.review_threshold}
          </div>
          <table className="eve-table w-full mt-2">
            <thead>
              <tr>
                <th>KPI</th>
                <th className="text-end">Raw</th>
                <th className="text-end">Score</th>
                <th className="text-end">Weight</th>
              </tr>
            </thead>
            <tbody>
              {rank.breakdown.map((b) => (
                <tr key={b.label}>
                  <td>{b.label}</td>
                  <td className="text-end">{typeof b.raw_value === "number" && b.raw_value > 1000 ? fmtIsk(b.raw_value) : b.raw_value.toFixed(2)}</td>
                  <td className="text-end">{b.score.toFixed(1)}</td>
                  <td className="text-end">{b.weight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {config ? (
        <div className="border border-[var(--edge-dim)] p-2 overflow-auto min-h-0">
          <SectionHead>KPI configuration (directors)</SectionHead>
          <div className="flex gap-2 mb-2">
            <label>
              Admit ≥
              <input
                className="eve-input w-16 ml-1"
                type="number"
                value={config.admit_threshold}
                onChange={(e) =>
                  setConfig({ ...config, admit_threshold: Number(e.target.value) || 0 })
                }
              />
            </label>
            <label>
              Review ≥
              <input
                className="eve-input w-16 ml-1"
                type="number"
                value={config.review_threshold}
                onChange={(e) =>
                  setConfig({ ...config, review_threshold: Number(e.target.value) || 0 })
                }
              />
            </label>
            <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void saveConfig()} disabled={saving}>
              {saving ? "Saving…" : "Save KPIs"}
            </button>
          </div>
          <table className="eve-table w-full">
            <thead>
              <tr>
                <th>KPI</th>
                <th>Active</th>
                <th className="text-end">Weight</th>
                <th className="text-end">Target</th>
              </tr>
            </thead>
            <tbody>
              {config.kpis.map((k, idx) => (
                <tr key={k.id}>
                  <td>{k.label}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={k.active}
                      onChange={(e) => {
                        const kpis = [...config.kpis];
                        kpis[idx] = { ...k, active: e.target.checked };
                        setConfig({ ...config, kpis });
                      }}
                    />
                  </td>
                  <td className="text-end">
                    <input
                      className="eve-input w-14 text-right"
                      type="number"
                      step="0.1"
                      value={k.weight}
                      onChange={(e) => {
                        const kpis = [...config.kpis];
                        kpis[idx] = { ...k, weight: Number(e.target.value) || 0 };
                        setConfig({ ...config, kpis });
                      }}
                    />
                  </td>
                  <td className="text-end">
                    <input
                      className="eve-input w-24 text-right"
                      type="number"
                      value={k.target_value}
                      onChange={(e) => {
                        const kpis = [...config.kpis];
                        kpis[idx] = { ...k, target_value: Number(e.target.value) || 0 };
                        setConfig({ ...config, kpis });
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-[var(--text-muted)]">KPI config visible to directors only.</p>
      )}
    </div>
  );
}

function StandingsPanel() {
  const [data, setData] = useState<{
    count: number;
    positive_count: number;
    negative_count: number;
    top_allies: { from_name: string; from_type: string; standing: number }[];
    top_hostiles: { from_name: string; from_type: string; standing: number }[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    const res = await fetch("/api/people/standings", { cache: "no-store" });
    if (res.ok) setData(await res.json());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sync = async () => {
    setLoading(true);
    setError("");
    setNote("");
    try {
      const res = await fetch("/api/people/standings/sync", { method: "POST" });
      const body = await res.json();
      if (!res.ok) {
        setError(body.detail || "Sync failed");
        return;
      }
      setNote(`Synced ${body.count} standings.`);
      await load();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full text-[11px]">
      <StatusStrip>
        ESI character standings · {data?.count ?? 0} contacts · +{data?.positive_count ?? 0} / −
        {data?.negative_count ?? 0}
      </StatusStrip>
      <button type="button" className="eve-btn eve-btn-primary text-sm self-start" onClick={() => void sync()} disabled={loading}>
        {loading ? "Syncing…" : "Sync standings from ESI"}
      </button>
      <p className="text-[10px] text-[var(--text-muted)]">
        Requires <code>esi-characters.read_standings.v1</code> on your SSO token.
      </p>
      {error ? <p className="text-[var(--danger)]">{error}</p> : null}
      {note ? <p className="text-[var(--ok)]">{note}</p> : null}
      <div className="grid grid-cols-2 gap-2 min-h-0 flex-1 overflow-auto">
        <div>
          <SectionHead>Top allies</SectionHead>
          <ul className="space-y-0.5">
            {(data?.top_allies || []).map((c) => (
              <li key={`${c.from_type}-${c.from_name}`} className="flex justify-between">
                <span>
                  {c.from_name} <span className="text-[var(--text-muted)]">({c.from_type})</span>
                </span>
                <span className="text-[var(--ok)]">{c.standing.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <SectionHead>Top hostiles</SectionHead>
          <ul className="space-y-0.5">
            {(data?.top_hostiles || []).map((c) => (
              <li key={`${c.from_type}-${c.from_name}`} className="flex justify-between">
                <span>
                  {c.from_name} <span className="text-[var(--text-muted)]">({c.from_type})</span>
                </span>
                <span className="text-[var(--danger)]">{c.standing.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function CalendarPanel() {
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [data, setData] = useState<{
    month_label: string;
    weeks: { date: string; in_month: boolean; is_today: boolean; events: { title: string; kind: string; time?: string }[]; event_count: number }[][];
    summary: { total_events: number; calendar: number; moon: number; fuel: number };
    events: { date: string; title: string; kind: string; time?: string }[];
  } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/people/calendar?month=${month}`, { cache: "no-store" });
      if (res.ok) {
        const body = await res.json();
        setData(body);
        setSelected(null);
      }
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    void load();
  }, [load]);

  const shiftMonth = (delta: number) => {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  };

  const dayEvents = useMemo(() => {
    if (!data || !selected) return [];
    return data.events.filter((e) => e.date === selected);
  }, [data, selected]);

  const kindColor = (kind: string) => {
    if (kind === "fuel") return "bg-[var(--danger)]";
    if (kind.startsWith("moon")) return "bg-[var(--warn)]";
    return "bg-[var(--accent)]";
  };

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full text-[11px]">
      <StatusStrip>
        {data?.month_label || month} · {data?.summary.total_events ?? 0} events (ESI calendar, moon timing, fuel)
      </StatusStrip>
      <div className="flex gap-2 items-center">
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => shiftMonth(-1)}>
          ←
        </button>
        <strong className="flex-1 text-center">{data?.month_label || month}</strong>
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => shiftMonth(1)}>
          →
        </button>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void load()} disabled={loading}>
          {loading ? "…" : "Refresh"}
        </button>
      </div>
      <div className="grid grid-cols-7 gap-px bg-[var(--edge-dim)] border border-[var(--edge-dim)] text-[10px]">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="bg-[var(--panel)] p-1 text-center text-[var(--text-muted)]">
            {d}
          </div>
        ))}
        {(data?.weeks || []).flat().map((day) => (
          <button
            key={day.date}
            type="button"
            onClick={() => setSelected(day.date)}
            className={`bg-[var(--panel)] p-1 min-h-[52px] text-left align-top ${
              !day.in_month ? "opacity-40" : ""
            } ${day.is_today ? "ring-1 ring-[var(--accent)]" : ""} ${
              selected === day.date ? "bg-[var(--panel-inset)]" : ""
            }`}
          >
            <div className="font-semibold">{day.date.slice(8)}</div>
            <div className="flex flex-wrap gap-0.5 mt-0.5">
              {day.events.slice(0, 3).map((e, i) => (
                <span key={i} className={`w-1.5 h-1.5 rounded-full ${kindColor(e.kind)}`} title={e.title} />
              ))}
            </div>
          </button>
        ))}
      </div>
      {selected ? (
        <div className="border border-[var(--edge-dim)] p-2 overflow-auto max-h-32">
          <SectionHead>{selected}</SectionHead>
          {dayEvents.length ? (
            <ul className="space-y-0.5">
              {dayEvents.map((e, i) => (
                <li key={i}>
                  <span className="text-[var(--text-muted)]">{e.time || "—"}</span> {e.title}{" "}
                  <span className="text-[9px] text-[var(--text-muted)]">({e.kind})</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[var(--text-muted)]">No events.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
