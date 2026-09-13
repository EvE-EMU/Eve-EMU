"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useAuth } from "@/components/AuthProvider";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { SectionHead, StatusStrip } from "@/components/ui";

type EligibleLoss = {
  killmail_id: number;
  killmail_hash: string;
  character_id: number;
  character_name: string;
  ship_type_id?: number;
  ship_type_name: string;
  killed_at: string | null;
  solar_system_name: string;
  zkill_url: string;
  submitted: boolean;
};

type FitModule = {
  type_id: number;
  type_name: string;
  flag_label: string;
  quantity: number;
};

type Preview = {
  ok: boolean;
  error?: string;
  killmail_id: number;
  character_id: number;
  ship_type_id: number;
  ship_type_name: string;
  solar_system_name: string;
  killed_at: string | null;
  total_value_isk: string;
  srp_amount_isk: string;
  fit_modules: FitModule[];
  fit_grade: "doctrine" | "meta" | "shitfit" | string;
  doctrine_name: string;
  doctrine_slug: string;
  doctrine_match_pct: number;
  matched_modules: number;
  expected_modules: number;
  rate_label: string | null;
  eligible: boolean;
  block_reason: string;
  already_submitted: boolean;
  claim_status: string | null;
  zkill_url: string;
};

type Claim = {
  id: number;
  killmail_id: number;
  character_name: string;
  ship_type_name: string;
  total_value_isk: string;
  srp_amount_isk: string;
  fit_grade: string;
  doctrine_match_pct: number;
  status: string;
  zkill_url: string;
  killed_at: string | null;
  submitted_at: string | null;
};

function fmtIsk(v: string | number) {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)} T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  return n.toLocaleString();
}

function fmtWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function FitGradeBadge({ grade }: { grade: string }) {
  const label =
    grade === "doctrine" ? "Doctrine fit" : grade === "meta" ? "Meta fit" : grade === "shitfit" ? "Shitfit" : grade;
  return (
    <span
      className={clsx(
        "inline-block px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide",
        grade === "doctrine" && "bg-[var(--ok)]/20 text-[var(--ok)]",
        grade === "meta" && "bg-[var(--warn)]/20 text-[var(--warn)]",
        grade === "shitfit" && "bg-[var(--danger)]/20 text-[var(--danger)]",
        !["doctrine", "meta", "shitfit"].includes(grade) && "bg-[var(--border)] text-[var(--text-muted)]"
      )}
    >
      {label}
    </span>
  );
}

function KillmailFitPanel({ preview }: { preview: Preview | null }) {
  if (!preview?.ok) {
    return (
      <p className="text-[11px] text-[var(--text-muted)] p-2">
        {preview?.error ?? "Select a recent loss to preview the fitted modules and SRP quote."}
      </p>
    );
  }

  return (
    <div className="eve-ship-fitting-panel p-2 text-[11px] space-y-3">
      <div className="flex items-start gap-3">
        <EveTypeIcon typeId={preview.ship_type_id} size={48} preferRender />
        <div className="flex-1 min-w-0">
          <div className="font-medium">{preview.ship_type_name}</div>
          <div className="text-[10px] text-[var(--text-muted)]">
            {preview.solar_system_name || "Unknown system"} · {fmtWhen(preview.killed_at)}
          </div>
          <div className="mt-1 flex flex-wrap gap-2 items-center">
            <FitGradeBadge grade={preview.fit_grade} />
            {preview.doctrine_name ? (
              <span className="text-[10px] text-[var(--text-muted)]">
                vs {preview.doctrine_name} ({preview.doctrine_match_pct}% · {preview.matched_modules}/
                {preview.expected_modules} modules)
              </span>
            ) : null}
          </div>
        </div>
        <div className="text-right text-[10px]">
          <div className="text-[var(--text-muted)]">Loss value</div>
          <div className="tabular-nums">{fmtIsk(preview.total_value_isk)}</div>
          <div className="text-[var(--text-muted)] mt-1">SRP quote</div>
          <div className="tabular-nums text-[var(--link)] font-medium">{fmtIsk(preview.srp_amount_isk)}</div>
          {preview.rate_label ? (
            <div className="text-[9px] text-[var(--text-muted)] mt-0.5">{preview.rate_label}</div>
          ) : null}
        </div>
      </div>

      {preview.fit_modules.length ? (
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th className="w-8" />
              <th>Module</th>
              <th>Slot</th>
              <th className="text-right w-10">Qty</th>
            </tr>
          </thead>
          <tbody>
            {preview.fit_modules.map((mod) => (
              <tr key={`${mod.type_id}-${mod.flag_label}`}>
                <td>
                  <EveTypeIcon typeId={mod.type_id} size={20} preferRender />
                </td>
                <td>{mod.type_name}</td>
                <td className="text-[var(--text-muted)]">{mod.flag_label}</td>
                <td className="text-right tabular-nums">{mod.quantity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-[var(--text-muted)]">No fitted modules recorded on this killmail.</p>
      )}

      {!preview.eligible && preview.block_reason ? (
        <p className="text-[10px] text-[var(--danger)]">{preview.block_reason}</p>
      ) : null}
    </div>
  );
}

export function SrpProgramPanel() {
  const { session } = useAuth();
  const [tab, setTab] = useState<"submit" | "claims">("submit");
  const [losses, setLosses] = useState<EligibleLoss[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selected, setSelected] = useState<EligibleLoss | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [submitBusy, setSubmitBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scopeNote, setScopeNote] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadLosses = useCallback(async () => {
    const res = await fetch("/api/tools/srp/eligible-losses", { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) {
      setLosses([]);
      setScopeNote("Unable to load losses — log in with member access and grant killmail scope.");
      return;
    }
    const data = (await res.json()) as { losses: EligibleLoss[]; scope_note?: string };
    setLosses(data.losses || []);
    setScopeNote(data.scope_note ?? null);
  }, []);

  const loadClaims = useCallback(async () => {
    const res = await fetch("/api/tools/srp/claims", { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) {
      setClaims([]);
      return;
    }
    setClaims((await res.json()) as Claim[]);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([loadLosses(), loadClaims()]);
    } catch {
      setError("Failed to load SRP data.");
    } finally {
      setLoading(false);
    }
  }, [loadLosses, loadClaims]);

  useEffect(() => {
    if (session.authenticated) void loadAll();
  }, [session.authenticated, loadAll]);

  const loadPreview = useCallback(async (loss: EligibleLoss) => {
    setSelected(loss);
    setPreviewBusy(true);
    setMessage(null);
    try {
      const q = new URLSearchParams({
        killmail_id: String(loss.killmail_id),
        killmail_hash: loss.killmail_hash,
        character_id: String(loss.character_id),
      });
      const res = await fetch(`/api/tools/srp/preview?${q}`, { cache: "no-store", credentials: "same-origin" });
      const data = (await res.json()) as Preview;
      setPreview(data);
    } catch {
      setPreview({ ok: false, error: "Preview failed." } as Preview);
    } finally {
      setPreviewBusy(false);
    }
  }, []);

  const submit = async () => {
    if (!selected || !preview?.ok || !preview.eligible || preview.already_submitted) return;
    setSubmitBusy(true);
    setMessage(null);
    try {
      const res = await fetch("/api/tools/srp/submit", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          killmail_id: selected.killmail_id,
          killmail_hash: selected.killmail_hash,
          character_id: selected.character_id,
          notes,
        }),
      });
      const data = (await res.json()) as { detail?: string; srp_amount_isk?: string };
      if (!res.ok) {
        setMessage(data.detail || "Submission failed.");
        return;
      }
      setMessage(`SRP claim submitted — ${fmtIsk(data.srp_amount_isk || preview.srp_amount_isk)} ISK pending review.`);
      setNotes("");
      await loadAll();
      if (selected) void loadPreview(selected);
    } catch {
      setMessage("Submission failed.");
    } finally {
      setSubmitBusy(false);
    }
  };

  const pendingClaims = useMemo(() => claims.filter((c) => c.status === "pending").length, [claims]);

  if (!session.authenticated) {
    return <p className="text-[11px] text-[var(--text-muted)] p-3">Log in to submit ship replacement claims.</p>;
  }

  if (loading && !losses.length && !claims.length) {
    return <p className="text-[11px] text-[var(--text-muted)] p-3">Loading SRP losses from ESI…</p>;
  }

  return (
    <div className="text-[11px] flex flex-col h-full min-h-0 p-1 gap-2">
      <StatusStrip>
        Pull recent losses from ESI + audit cache · Fit graded vs coalition doctrines · Payout from admin rates
      </StatusStrip>

      <div className="flex gap-2 text-[10px]">
        <button
          type="button"
          className={clsx("eve-btn-sm", tab === "submit" && "eve-btn-primary")}
          onClick={() => setTab("submit")}
        >
          Submit claim
        </button>
        <button
          type="button"
          className={clsx("eve-btn-sm", tab === "claims" && "eve-btn-primary")}
          onClick={() => setTab("claims")}
        >
          My claims {pendingClaims ? `(${pendingClaims} pending)` : ""}
        </button>
        <button type="button" className="eve-btn-sm ml-auto" onClick={() => void loadAll()}>
          Refresh
        </button>
      </div>

      {error ? <p className="text-[var(--danger)]">{error}</p> : null}
      {scopeNote ? <p className="text-[10px] text-[var(--warn)]">{scopeNote}</p> : null}
      {message ? <p className="text-[10px] text-[var(--ok)]">{message}</p> : null}

      {tab === "submit" ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 flex-1 min-h-0 overflow-hidden">
          <div className="flex flex-col min-h-0 border border-[var(--border)] rounded">
            <SectionHead>Recent losses (roster)</SectionHead>
            <div className="overflow-auto flex-1 max-h-[320px]">
              <table className="eve-table w-full text-[10px]">
                <thead>
                  <tr>
                    <th>Pilot</th>
                    <th>Ship</th>
                    <th>When</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {losses.map((loss) => (
                    <tr
                      key={loss.killmail_id}
                      className={clsx(
                        "cursor-pointer hover:bg-[var(--surface-elevated)]",
                        selected?.killmail_id === loss.killmail_id && "bg-[var(--surface-elevated)]"
                      )}
                      onClick={() => void loadPreview(loss)}
                    >
                      <td>{loss.character_name}</td>
                      <td>{loss.ship_type_name || "—"}</td>
                      <td className="text-[var(--text-muted)] whitespace-nowrap">{fmtWhen(loss.killed_at)}</td>
                      <td>
                        {loss.submitted ? (
                          <span className="text-[var(--text-muted)]">Submitted</span>
                        ) : (
                          <span className="text-[var(--link)]">Preview</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!losses.length ? (
                <p className="p-2 text-[var(--text-muted)]">No recent losses found. Sync audit or grant killmail scope.</p>
              ) : null}
            </div>
          </div>

          <div className="flex flex-col min-h-0 border border-[var(--border)] rounded">
            <SectionHead>Fit &amp; SRP quote</SectionHead>
            <div className="overflow-auto flex-1 max-h-[320px]">
              {previewBusy ? (
                <p className="p-2 text-[var(--text-muted)]">Analyzing killmail…</p>
              ) : (
                <KillmailFitPanel preview={preview} />
              )}
            </div>
            {preview?.ok && !preview.already_submitted && preview.eligible ? (
              <div className="p-2 border-t border-[var(--border)] space-y-2">
                <textarea
                  className="eve-input w-full text-[10px] min-h-[48px]"
                  placeholder="Optional notes for SRP directors…"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <button
                  type="button"
                  className="eve-btn-sm eve-btn-primary"
                  disabled={submitBusy || !selected}
                  onClick={() => void submit()}
                >
                  {submitBusy ? "Submitting…" : "Submit SRP claim"}
                </button>
              </div>
            ) : null}
            {preview?.already_submitted ? (
              <p className="p-2 text-[10px] text-[var(--text-muted)] border-t border-[var(--border)]">
                Already submitted — status: {preview.claim_status}
              </p>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="overflow-auto border border-[var(--border)] rounded">
          <table className="eve-table w-full text-[10px]">
            <thead>
              <tr>
                <th>Pilot</th>
                <th>Ship</th>
                <th>Fit</th>
                <th>Loss</th>
                <th>SRP</th>
                <th>Status</th>
                <th>zKill</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((row) => (
                <tr key={row.id}>
                  <td>{row.character_name}</td>
                  <td>{row.ship_type_name}</td>
                  <td>
                    <FitGradeBadge grade={row.fit_grade} />
                    {row.doctrine_match_pct > 0 ? (
                      <span className="text-[9px] text-[var(--text-muted)] ml-1">{row.doctrine_match_pct}%</span>
                    ) : null}
                  </td>
                  <td className="tabular-nums">{fmtIsk(row.total_value_isk)}</td>
                  <td className="tabular-nums text-[var(--link)]">{fmtIsk(row.srp_amount_isk)}</td>
                  <td
                    className={clsx(
                      row.status === "pending" && "text-[var(--warn)]",
                      row.status === "paid" && "text-[var(--ok)]"
                    )}
                  >
                    {row.status}
                  </td>
                  <td>
                    {row.zkill_url ? (
                      <a href={row.zkill_url} className="text-[var(--link)]" target="_blank" rel="noreferrer">
                        view
                      </a>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!claims.length ? <p className="p-2 text-[var(--text-muted)]">No SRP claims yet.</p> : null}
        </div>
      )}
    </div>
  );
}
