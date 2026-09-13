"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type {
  Invoice,
  MiningLog,
  OrgSettings,
  StructureTaxRule,
} from "@/lib/api";
import {
  fetchInfrastructure,
  fetchHrBlacklist,
  fetchHrFlags,
  fetchHrRoleTitles,
  createHrRoleTitle,
  fetchHrAuditRules,
  createHrAuditRule,
  patchHrAuditRule,
  deleteHrAuditRule,
  patchHrLeaveStatus,
  patchSrpStatus,
  setServiceLock,
  fetchSrpRateRules,
  createSrpRateRule,
  patchSrpRateRule,
  deleteSrpRateRule,
  fetchBuildStructures,
  createBuildStructure,
  deleteBuildStructure,
  type InfrastructureStatus,
  type BuildStructureRow,
  type HrRoleTitleRow,
  type HrAuditRuleRow,
  type SrpRateRuleRow,
} from "@/lib/admin";
import { StorefrontAdminWindow } from "@/components/StorefrontAdminWindow";
import {
  EveTable,
  EveWindow,
  KpiStrip,
  KpiTile,
  SectionHead,
  StatusStrip,
} from "@/components/ui";
import { DesktopSurface } from "@/components/WindowManager";

type Leave = {
  id: number;
  character_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
};

type SrpRow = {
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
};

type SecurityFlag = {
  id: number;
  character_id: number;
  character_name: string;
  flag_key: string;
  severity: string;
  detail: string;
};

function fmtIsk(v: string | number) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString();
}

function RowActions({
  onApprove,
  onReject,
  disabled,
}: {
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex gap-1">
      <button type="button" className="eve-btn-sm eve-btn-primary" disabled={disabled} onClick={onApprove}>
        Approve
      </button>
      <button type="button" className="eve-btn-sm" disabled={disabled} onClick={onReject}>
        Reject
      </button>
    </div>
  );
}

function InfrastructureWindow() {
  const [data, setData] = useState<InfrastructureStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await fetchInfrastructure());
      setError(null);
    } catch {
      setError("Telemetry unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(t);
  }, [refresh]);

  return (
    <EveWindow
      id="admin-infra"
      title="Infrastructure telemetry"
      defaultX={4}
      defaultY={4}
      defaultWidth={420}
      defaultHeight={340}
      actions={
        <button type="button" className="eve-btn-sm" onClick={() => void refresh()}>
          Refresh
        </button>
      }
    >
      {error ? <p className="text-[var(--danger)] text-[11px]">{error}</p> : null}
      {data ? (
        <div className="space-y-2 text-[11px]">
          <KpiStrip>
            <KpiTile
              label="Redis"
              value={data.redis.reachable ? "Online" : "Down"}
              tone={data.redis.reachable ? "ok" : "danger"}
            />
            <KpiTile label="Workers" value={String(data.celery.workers_online)} tone="accent" />
            <KpiTile label="Active tasks" value={String(data.celery.active_task_count)} />
            <KpiTile label="Scheduled" value={String(data.celery.scheduled_count)} />
          </KpiStrip>
          <SectionHead>Redis</SectionHead>
          <p className="text-[var(--text-muted)]">
            Clients {data.redis.connected_clients ?? 0} · Memory {data.redis.used_memory_human || "—"}
          </p>
          <SectionHead>Celery workers</SectionHead>
          <ul className="text-[10px] text-[var(--text-muted)] max-h-[72px] overflow-auto eve-scroll">
            {data.celery.worker_names.length ? (
              data.celery.worker_names.map((w) => <li key={w}>{w}</li>)
            ) : (
              <li>No workers responding</li>
            )}
          </ul>
          <SectionHead>Beat schedule</SectionHead>
          <table className="eve-table text-[10px]">
            <thead>
              <tr>
                <th>Job</th>
                <th>Task</th>
              </tr>
            </thead>
            <tbody>
              {data.celery.beat_schedule.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="font-mono text-[9px] text-[var(--text-dim)]">{row.task.split(".").pop()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[9px] text-[var(--text-muted)]">
            Updated {new Date(data.checked_at).toLocaleTimeString()}
          </p>
        </div>
      ) : (
        <p className="text-[var(--text-muted)] text-[11px]">Loading telemetry…</p>
      )}
    </EveWindow>
  );
}

function HrDirectorateWindow({
  leaves: initialLeaves,
  onLeavesChange,
}: {
  leaves: Leave[];
  onLeavesChange: (rows: Leave[]) => void;
}) {
  const [tab, setTab] = useState<"leaves" | "blacklist" | "flags" | "titles" | "audit-rules">("leaves");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState<"date" | "name">("date");
  const [blacklist, setBlacklist] = useState<{ character_name: string; reason: string; added_by: string }[]>([]);
  const [flags, setFlags] = useState<{ character_name: string; flag_label: string; color: string; notes: string }[]>([]);
  const [roleTitles, setRoleTitles] = useState<HrRoleTitleRow[]>([]);
  const [auditRules, setAuditRules] = useState<HrAuditRuleRow[]>([]);
  const [ruleForm, setRuleForm] = useState({
    rule_key: "",
    name: "",
    description: "",
    rule_type: "mail_subject" as HrAuditRuleRow["rule_type"],
    severity: "warn" as HrAuditRuleRow["severity"],
    match_json: '{"patterns":["spy","recruit"]}',
    webhook_url: "",
    notify_in_app: true,
    cooldown_hours: 24,
  });
  const [titleForm, setTitleForm] = useState({ corporation_id: "", title_id: "", title_name: "", description: "" });
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    void fetchHrBlacklist().then(setBlacklist);
    void fetchHrFlags().then(setFlags);
    void fetchHrRoleTitles().then(setRoleTitles);
    void fetchHrAuditRules().then(setAuditRules);
  }, []);

  const leaves = useMemo(() => {
    let rows = [...initialLeaves];
    if (filter !== "all") rows = rows.filter((l) => l.status === filter);
    rows.sort((a, b) =>
      sort === "name"
        ? a.character_name.localeCompare(b.character_name)
        : b.start_date.localeCompare(a.start_date)
    );
    return rows;
  }, [initialLeaves, filter, sort]);

  const updateLeave = async (id: number, status: string) => {
    setBusy(id);
    try {
      await patchHrLeaveStatus(id, status);
      onLeavesChange(initialLeaves.map((l) => (l.id === id ? { ...l, status } : l)));
    } finally {
      setBusy(null);
    }
  };

  return (
    <EveWindow
      id="hr-directorate"
      title="HR directorate"
      defaultX={432}
      defaultY={4}
      defaultWidth={440}
      defaultHeight={380}
    >
      <div className="flex gap-1 mb-2">
        {(["leaves", "blacklist", "flags", "titles", "audit-rules"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={clsx("eve-btn-sm", tab === t && "eve-btn-primary")}
            onClick={() => setTab(t)}
          >
            {t === "leaves"
              ? "Leave requests"
              : t === "blacklist"
                ? "Blacklist"
                : t === "flags"
                  ? "Account flags"
                  : t === "titles"
                    ? "HR role titles"
                    : "Audit alerts"}
          </button>
        ))}
      </div>
      {tab === "leaves" ? (
        <>
          <div className="flex gap-2 mb-2 text-[10px]">
            <label>
              Filter{" "}
              <select className="eve-select ml-1" value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="all">All</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </label>
            <label>
              Sort{" "}
              <select className="eve-select ml-1" value={sort} onChange={(e) => setSort(e.target.value as "date" | "name")}>
                <option value="date">Start date</option>
                <option value="name">Character</option>
              </select>
            </label>
          </div>
          <EveTable headers={[{ label: "Pilot" }, { label: "Dates" }, { label: "Status" }, { label: "Actions" }]}>
            {leaves.map((l) => (
              <tr key={l.id}>
                <td>{l.character_name}</td>
                <td className="text-[10px] text-[var(--text-muted)]">
                  {l.start_date} → {l.end_date}
                </td>
                <td className={clsx(l.status === "pending" && "text-[var(--warn)]", l.status === "approved" && "text-[var(--ok)]")}>
                  {l.status}
                </td>
                <td>
                  {l.status === "pending" ? (
                    <RowActions
                      disabled={busy === l.id}
                      onApprove={() => void updateLeave(l.id, "approved")}
                      onReject={() => void updateLeave(l.id, "rejected")}
                    />
                  ) : null}
                </td>
              </tr>
            ))}
          </EveTable>
        </>
      ) : null}
      {tab === "blacklist" ? (
        <EveTable headers={[{ label: "Character" }, { label: "Reason" }, { label: "Added by" }]}>
          {blacklist.map((b, i) => (
            <tr key={i}>
              <td className="text-[var(--danger)]">{b.character_name}</td>
              <td>{b.reason}</td>
              <td className="text-[var(--text-muted)]">{b.added_by}</td>
            </tr>
          ))}
        </EveTable>
      ) : null}
      {tab === "flags" ? (
        <EveTable headers={[{ label: "Character" }, { label: "Flag" }, { label: "Notes" }]}>
          {flags.map((f, i) => (
            <tr key={i}>
              <td>{f.character_name}</td>
              <td className={clsx(f.color === "warn" && "text-[var(--warn)]", f.color === "danger" && "text-[var(--danger)]")}>
                {f.flag_label}
              </td>
              <td className="text-[10px] text-[var(--text-muted)]">{f.notes}</td>
            </tr>
          ))}
        </EveTable>
      ) : null}
      {tab === "titles" ? (
        <div className="space-y-3 text-[10px]">
          <p className="text-[var(--text-muted)]">
            Corporation titles that grant HR pilot lookup. Title IDs match in-game corp titles; sync runs on character audit.
          </p>
          <form
            className="grid grid-cols-2 gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void createHrRoleTitle({
                corporation_id: Number(titleForm.corporation_id),
                title_id: Number(titleForm.title_id),
                title_name: titleForm.title_name,
                description: titleForm.description,
              }).then((row) => {
                setRoleTitles((prev) => [...prev, row as HrRoleTitleRow]);
                setTitleForm({ corporation_id: "", title_id: "", title_name: "", description: "" });
              });
            }}
          >
            <input className="eve-input" placeholder="Corporation ID" value={titleForm.corporation_id} onChange={(e) => setTitleForm((f) => ({ ...f, corporation_id: e.target.value }))} required />
            <input className="eve-input" placeholder="Title ID" value={titleForm.title_id} onChange={(e) => setTitleForm((f) => ({ ...f, title_id: e.target.value }))} required />
            <input className="eve-input col-span-2" placeholder="Title name" value={titleForm.title_name} onChange={(e) => setTitleForm((f) => ({ ...f, title_name: e.target.value }))} required />
            <input className="eve-input col-span-2" placeholder="Description" value={titleForm.description} onChange={(e) => setTitleForm((f) => ({ ...f, description: e.target.value }))} />
            <button type="submit" className="eve-btn-sm eve-btn-primary col-span-2">Add HR role title</button>
          </form>
          <EveTable headers={[{ label: "Corp ID" }, { label: "Title ID" }, { label: "Name" }, { label: "Active" }]}>
            {roleTitles.map((t) => (
              <tr key={t.id}>
                <td>{t.corporation_id}</td>
                <td>{t.title_id}</td>
                <td>{t.title_name}</td>
                <td>{t.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </EveTable>
        </div>
      ) : null}
      {tab === "audit-rules" ? (
        <div className="space-y-3 text-[10px]">
          <p className="text-[var(--text-muted)]">
            Configure webhook and in-app alerts for suspicious wallet activity, mail subjects, blacklist contacts, and
            interaction thresholds. Rules run on each character audit sync.
          </p>
          <form
            className="grid grid-cols-2 gap-2 border border-[var(--border)] p-2"
            onSubmit={(e) => {
              e.preventDefault();
              void createHrAuditRule({ ...ruleForm, enabled: true }).then((row) => {
                setAuditRules((prev) => [...prev, row as HrAuditRuleRow]);
                setRuleForm((f) => ({ ...f, rule_key: "", name: "" }));
              });
            }}
          >
            <input
              className="eve-input"
              placeholder="Rule key (unique)"
              value={ruleForm.rule_key}
              onChange={(e) => setRuleForm((f) => ({ ...f, rule_key: e.target.value }))}
              required
            />
            <input
              className="eve-input"
              placeholder="Display name"
              value={ruleForm.name}
              onChange={(e) => setRuleForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
            <select
              className="eve-select"
              value={ruleForm.rule_type}
              onChange={(e) =>
                setRuleForm((f) => ({
                  ...f,
                  rule_type: e.target.value as HrAuditRuleRow["rule_type"],
                }))
              }
            >
              <option value="mail_subject">Mail subject</option>
              <option value="wallet_ref_type">Wallet ref type</option>
              <option value="blacklist_contact">Blacklist contact</option>
              <option value="wallet_drop">Wallet drop</option>
              <option value="interaction_threshold">Interaction threshold</option>
            </select>
            <select
              className="eve-select"
              value={ruleForm.severity}
              onChange={(e) =>
                setRuleForm((f) => ({ ...f, severity: e.target.value as HrAuditRuleRow["severity"] }))
              }
            >
              <option value="warn">Warn</option>
              <option value="critical">Critical</option>
            </select>
            <input
              className="eve-input col-span-2"
              placeholder="Discord webhook URL (optional)"
              value={ruleForm.webhook_url}
              onChange={(e) => setRuleForm((f) => ({ ...f, webhook_url: e.target.value }))}
            />
            <textarea
              className="eve-input col-span-2 font-mono text-[9px] min-h-[56px]"
              placeholder='match_json e.g. {"patterns":["recruit"]} or {"ref_types":["bounty_prizes"]}'
              value={ruleForm.match_json}
              onChange={(e) => setRuleForm((f) => ({ ...f, match_json: e.target.value }))}
            />
            <label className="col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={ruleForm.notify_in_app}
                onChange={(e) => setRuleForm((f) => ({ ...f, notify_in_app: e.target.checked }))}
              />
              Also create in-app security flag
            </label>
            <button type="submit" className="eve-btn-sm eve-btn-primary col-span-2">
              Add audit rule
            </button>
          </form>
          <EveTable
            headers={[
              { label: "Rule" },
              { label: "Type" },
              { label: "Webhook" },
              { label: "On" },
              { label: "Actions" },
            ]}
          >
            {auditRules.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <div>{rule.name}</div>
                  <div className={clsx("text-[9px]", rule.severity === "critical" && "text-[var(--danger)]")}>
                    {rule.severity}
                  </div>
                </td>
                <td className="font-mono text-[9px]">{rule.rule_type}</td>
                <td className="text-[9px] truncate max-w-[100px]" title={rule.webhook_url}>
                  {rule.webhook_url ? "Set" : "—"}
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={rule.enabled}
                    onChange={(e) =>
                      void patchHrAuditRule(rule.id, { enabled: e.target.checked }).then((updated) =>
                        setAuditRules((prev) =>
                          prev.map((r) => (r.id === rule.id ? (updated as HrAuditRuleRow) : r))
                        )
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="eve-btn-sm text-[var(--danger)]"
                    onClick={() =>
                      void deleteHrAuditRule(rule.id).then(() =>
                        setAuditRules((prev) => prev.filter((r) => r.id !== rule.id))
                      )
                    }
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </EveTable>
        </div>
      ) : null}
    </EveWindow>
  );
}

function SrpDirectorateWindow({
  rows: initialRows,
  onRowsChange,
}: {
  rows: SrpRow[];
  onRowsChange: (rows: SrpRow[]) => void;
}) {
  const [filter, setFilter] = useState("pending");
  const [busy, setBusy] = useState<number | null>(null);

  const rows = useMemo(() => {
    const list = filter === "all" ? initialRows : initialRows.filter((r) => r.status === filter);
    return [...list].sort((a, b) => b.id - a.id);
  }, [initialRows, filter]);

  const update = async (id: number, status: string) => {
    setBusy(id);
    try {
      await patchSrpStatus(id, status);
      onRowsChange(initialRows.map((r) => (r.id === id ? { ...r, status } : r)));
    } finally {
      setBusy(null);
    }
  };

  return (
    <EveWindow
      id="srp-program"
      title="SRP processing queue"
      defaultX={880}
      defaultY={4}
      defaultWidth={520}
      defaultHeight={380}
    >
      <div className="mb-2 flex gap-2 items-center text-[10px]">
        <span className="text-[var(--text-muted)]">Filter</span>
        <select className="eve-select" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All claims</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="paid">Paid</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <EveTable
        headers={[
          { label: "Pilot" },
          { label: "Ship" },
          { label: "Fit" },
          { label: "Loss", align: "right" },
          { label: "SRP", align: "right" },
          { label: "Status" },
          { label: "Actions" },
        ]}
      >
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.character_name}</td>
            <td>{row.ship_type_name}</td>
            <td>
              <span
                className={clsx(
                  "uppercase text-[9px]",
                  row.fit_grade === "doctrine" && "text-[var(--ok)]",
                  row.fit_grade === "meta" && "text-[var(--warn)]",
                  row.fit_grade === "shitfit" && "text-[var(--danger)]"
                )}
              >
                {row.fit_grade || "—"}
              </span>
              {row.doctrine_match_pct > 0 ? (
                <span className="text-[9px] text-[var(--text-muted)] ml-1">{row.doctrine_match_pct}%</span>
              ) : null}
            </td>
            <td className="num">{fmtIsk(row.total_value_isk)}</td>
            <td className="num text-[var(--link)]">{fmtIsk(row.srp_amount_isk)}</td>
            <td className={clsx(row.status === "pending" && "text-[var(--warn)]", row.status === "paid" && "text-[var(--ok)]")}>
              {row.status}
            </td>
            <td>
              <div className="flex flex-wrap gap-1">
                {row.status === "pending" ? (
                  <RowActions
                    disabled={busy === row.id}
                    onApprove={() => void update(row.id, "approved")}
                    onReject={() => void update(row.id, "rejected")}
                  />
                ) : null}
                {row.status === "approved" ? (
                  <button type="button" className="eve-btn-sm eve-btn-primary" disabled={busy === row.id} onClick={() => void update(row.id, "paid")}>
                    Mark paid
                  </button>
                ) : null}
                {row.zkill_url ? (
                  <a href={row.zkill_url} className="eve-btn-sm text-[var(--link)]" target="_blank" rel="noreferrer">
                    zKill
                  </a>
                ) : null}
              </div>
            </td>
          </tr>
        ))}
      </EveTable>
    </EveWindow>
  );
}

function AuditDirectorWindow({ flags: initialFlags }: { flags: SecurityFlag[] }) {
  const [flags] = useState(initialFlags);
  const [assetQ, setAssetQ] = useState("");
  const [assetHits, setAssetHits] = useState<{ character_id: number; type_name: string; quantity: number }[]>([]);

  const searchAssets = async () => {
    if (!assetQ.trim()) return;
    const res = await fetch(`/api/audit/assets/search?q=${encodeURIComponent(assetQ)}`);
    if (res.ok) setAssetHits(await res.json());
  };

  return (
    <EveWindow id="admin-audit" title="Security audit flags" defaultX={4} defaultY={392} defaultWidth={420} defaultHeight={300}>
      <SectionHead>Active security flags</SectionHead>
      <ul className="max-h-[120px] overflow-auto eve-scroll text-[10px] space-y-1 mb-2">
        {flags.length ? (
          flags.map((f) => (
            <li key={f.id} className={f.severity === "critical" ? "text-[var(--danger)]" : "text-[var(--warn)]"}>
              {f.character_name}: {f.detail}
            </li>
          ))
        ) : (
          <li className="text-[var(--text-muted)]">No active flags</li>
        )}
      </ul>
      <SectionHead>Coalition asset search</SectionHead>
      <div className="flex gap-1 mb-1">
        <input className="eve-input flex-1" value={assetQ} onChange={(e) => setAssetQ(e.target.value)} placeholder="Module or hull name" />
        <button type="button" className="eve-btn-sm" onClick={() => void searchAssets()}>
          Search
        </button>
      </div>
      <ul className="text-[10px] text-[var(--text-muted)] max-h-[80px] overflow-auto eve-scroll">
        {assetHits.map((a, i) => (
          <li key={i}>
            {a.type_name} ×{a.quantity} — char {a.character_id}
          </li>
        ))}
      </ul>
    </EveWindow>
  );
}

function ServicesWindow({
  services,
}: {
  services: { id: number; label: string; url: string; description: string; service: string }[];
}) {
  const [locked, setLocked] = useState(false);
  const [lockReason, setLockReason] = useState("");
  const [busy, setBusy] = useState(false);

  const toggleLock = async () => {
    setBusy(true);
    try {
      const next = !locked;
      await setServiceLock(next, lockReason);
      setLocked(next);
    } finally {
      setBusy(false);
    }
  };

  return (
    <EveWindow id="services" title="Service registry & locks" defaultX={4} defaultY={704} defaultWidth={420} defaultHeight={280}>
      <ul className="text-[10px] space-y-1 mb-2">
        {services.map((s) => (
          <li key={s.id}>
            <a href={s.url} className="text-[var(--link)]" target="_blank" rel="noreferrer">
              {s.label}
            </a>
            <span className="text-[var(--text-muted)]"> · {s.service}</span>
          </li>
        ))}
      </ul>
      <SectionHead>Emergency service lock</SectionHead>
      <input
        className="eve-input w-full mb-1"
        placeholder="Lock reason (optional)"
        value={lockReason}
        onChange={(e) => setLockReason(e.target.value)}
      />
      <button type="button" className={clsx("eve-btn-sm", locked ? "eve-btn-primary" : "")} disabled={busy} onClick={() => void toggleLock()}>
        {locked ? "Release service sync lock" : "Apply emergency lock"}
      </button>
      {locked ? <p className="text-[var(--danger)] text-[10px] mt-1">External sync disabled</p> : null}
    </EveWindow>
  );
}

function RattingWindow({
  ratting,
}: {
  ratting: { id: number; period_label: string; rate_pct: string; status: string; total_bounty_isk: string; total_collected_isk: string }[];
}) {
  return (
    <EveWindow id="ratting-tax" title="Ratting tax periods" defaultX={432} defaultY={704} defaultWidth={440} defaultHeight={280}>
      <EveTable headers={[{ label: "Period" }, { label: "Rate" }, { label: "Bounty", align: "right" }, { label: "Collected", align: "right" }]}>
        {ratting.map((p) => (
          <tr key={p.id}>
            <td>{p.period_label}</td>
            <td>{p.rate_pct}%</td>
            <td className="num">{fmtIsk(p.total_bounty_isk)}</td>
            <td className="num text-[var(--ok)]">{fmtIsk(p.total_collected_isk)}</td>
          </tr>
        ))}
      </EveTable>
    </EveWindow>
  );
}

function SrpRatesWindow() {
  const [rules, setRules] = useState<SrpRateRuleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await fetchSrpRateRules());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addRule = async () => {
    setBusy(-1);
    try {
      const row = await createSrpRateRule({
        label: "New rate rule",
        ship_type_id: 0,
        ship_type_name: "",
        doctrine_slug: "",
        base_srp_isk: "200000000",
        max_percent: "80",
        doctrine_multiplier: "1",
        meta_multiplier: "0.75",
        shitfit_multiplier: "0",
        allow_shitfit: false,
        enabled: true,
        priority: 100,
      });
      setRules((prev) => [...prev, row]);
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (row: SrpRateRuleRow) => {
    setBusy(row.id);
    try {
      const updated = await patchSrpRateRule(row.id, { enabled: !row.enabled });
      setRules((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: number) => {
    setBusy(id);
    try {
      await deleteSrpRateRule(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } finally {
      setBusy(null);
    }
  };

  return (
    <EveWindow
      id="srp-rates"
      title="SRP rate rules"
      defaultX={440}
      defaultY={392}
      defaultWidth={520}
      defaultHeight={340}
    >
      <div className="mb-2 flex gap-2 text-[10px]">
        <button type="button" className="eve-btn-sm eve-btn-primary" disabled={busy !== null} onClick={() => void addRule()}>
          Add rule
        </button>
        <button type="button" className="eve-btn-sm" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-[10px] text-[var(--text-muted)]">Loading rates…</p>
      ) : (
        <EveTable
          headers={[
            { label: "Label" },
            { label: "Ship" },
            { label: "Base SRP", align: "right" },
            { label: "Mults" },
            { label: "On" },
            { label: "" },
          ]}
        >
          {rules.map((row) => (
            <tr key={row.id}>
              <td>{row.label}</td>
              <td className="text-[var(--text-muted)]">
                {row.ship_type_name || (row.ship_type_id ? `Type ${row.ship_type_id}` : "Any")}
                {row.doctrine_slug ? ` · ${row.doctrine_slug}` : ""}
              </td>
              <td className="num">{fmtIsk(row.base_srp_isk)}</td>
              <td className="text-[9px] text-[var(--text-muted)]">
                D×{row.doctrine_multiplier} M×{row.meta_multiplier}
                {row.max_percent ? ` cap ${row.max_percent}%` : ""}
              </td>
              <td>
                <button
                  type="button"
                  className="eve-btn-sm"
                  disabled={busy === row.id}
                  onClick={() => void toggle(row)}
                >
                  {row.enabled ? "Yes" : "No"}
                </button>
              </td>
              <td>
                <button type="button" className="eve-btn-sm text-[var(--danger)]" disabled={busy === row.id} onClick={() => void remove(row.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </EveTable>
      )}
      {!loading && !rules.length ? (
        <p className="text-[10px] text-[var(--text-muted)] mt-2">No SRP rates configured — add a rule or run seed.</p>
      ) : null}
    </EveWindow>
  );
}

function BuildStructuresWindow() {
  const [rows, setRows] = useState<BuildStructureRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    structure_id: "",
    structure_name: "",
    system_name: "",
    location_label: "",
    material_bonus_pct: "0",
    time_bonus_pct: "0",
    tax_pct: "0",
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await fetchBuildStructures());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <EveWindow
      id="admin-build-structures"
      title="Industrial build structures"
      defaultX={440}
      defaultY={4}
      defaultWidth={480}
      defaultHeight={420}
    >
      <p className="text-[10px] text-[var(--text-muted)] mb-2">
        Structures available in Build Planner — bonuses, tax, and stock location labels for members.
      </p>
      <div className="grid grid-cols-2 gap-1 mb-2 text-[10px]">
        <input className="eve-input" placeholder="Structure ID" value={form.structure_id} onChange={(e) => setForm({ ...form, structure_id: e.target.value })} />
        <input className="eve-input" placeholder="Name" value={form.structure_name} onChange={(e) => setForm({ ...form, structure_name: e.target.value })} />
        <input className="eve-input" placeholder="System" value={form.system_name} onChange={(e) => setForm({ ...form, system_name: e.target.value })} />
        <input className="eve-input" placeholder="Location label" value={form.location_label} onChange={(e) => setForm({ ...form, location_label: e.target.value })} />
        <input className="eve-input" placeholder="Mat bonus %" value={form.material_bonus_pct} onChange={(e) => setForm({ ...form, material_bonus_pct: e.target.value })} />
        <input className="eve-input" placeholder="Time bonus %" value={form.time_bonus_pct} onChange={(e) => setForm({ ...form, time_bonus_pct: e.target.value })} />
        <input className="eve-input" placeholder="Tax %" value={form.tax_pct} onChange={(e) => setForm({ ...form, tax_pct: e.target.value })} />
        <button
          type="button"
          className="eve-btn eve-btn-primary"
          onClick={() =>
            void createBuildStructure({
              structure_id: parseInt(form.structure_id, 10),
              structure_name: form.structure_name,
              system_name: form.system_name,
              location_label: form.location_label,
              material_bonus_pct: parseFloat(form.material_bonus_pct) || 0,
              time_bonus_pct: parseFloat(form.time_bonus_pct) || 0,
              tax_pct: parseFloat(form.tax_pct) || 0,
              has_manufacturing: true,
            }).then(() => refresh())
          }
        >
          Add structure
        </button>
      </div>
      {loading ? <p className="text-[var(--text-muted)]">Loading…</p> : null}
      <EveTable headers={[{ label: "Name" }, { label: "System" }, { label: "Mat%", align: "right" }, { label: "Tax%", align: "right" }, { label: "" }]}>
        {rows.map((r) => (
          <tr key={r.id}>
            <td>{r.structure_name}</td>
            <td>{r.system_name}</td>
            <td className="num">{r.material_bonus_pct}</td>
            <td className="num">{r.tax_pct}</td>
            <td>
              <button type="button" className="eve-btn-sm text-[var(--danger)]" onClick={() => void deleteBuildStructure(r.id).then(refresh)}>
                Delete
              </button>
            </td>
          </tr>
        ))}
      </EveTable>
    </EveWindow>
  );
}

function PniWindow({
  pni,
}: {
  pni: { id: number; period_label: string; status: string; total_income_isk: string; total_expense_isk: string }[];
}) {
  return (
    <EveWindow id="pni-statements" title="P&I statements" defaultX={880} defaultY={704} defaultWidth={420} defaultHeight={280}>
      {pni.map((s) => (
        <div key={s.id} className="border-b border-[var(--edge-dim)] py-1.5 text-[10px]">
          <strong>{s.period_label}</strong> · {s.status}
          <div className="text-[var(--text-muted)]">
            Income {fmtIsk(s.total_income_isk)} · Expense {fmtIsk(s.total_expense_isk)}
          </div>
        </div>
      ))}
    </EveWindow>
  );
}

export function AdministrationDirectorate({
  services,
  ratting,
  leaves: initialLeaves,
  pni,
  srp: initialSrp,
  settings,
  taxRules,
  logs,
  invoices,
  auditFlags,
  embedded,
}: {
  services: Awaited<ReturnType<typeof import("@/lib/api").fetchServiceLinks>>;
  ratting: Awaited<ReturnType<typeof import("@/lib/api").fetchRattingPeriods>>;
  leaves: Leave[];
  pni: Awaited<ReturnType<typeof import("@/lib/api").fetchPniStatements>>;
  srp: SrpRow[];
  settings: OrgSettings;
  taxRules: StructureTaxRule[];
  logs: MiningLog[];
  invoices: Invoice[];
  auditFlags: SecurityFlag[];
  embedded?: boolean;
}) {
  const [leaves, setLeaves] = useState(initialLeaves);
  const [srp, setSrp] = useState(initialSrp);

  const pendingSrp = srp.filter((r) => r.status === "pending").length;
  const pendingHr = leaves.filter((l) => l.status === "pending").length;
  const criticalFlags = auditFlags.filter((f) => f.severity === "critical").length;

  const adminWindows = (
    <>
        <InfrastructureWindow />
        <BuildStructuresWindow />
        <StorefrontAdminWindow />
        <HrDirectorateWindow leaves={leaves} onLeavesChange={setLeaves} />
        <SrpDirectorateWindow rows={srp} onRowsChange={setSrp} />
        <SrpRatesWindow />
        <AuditDirectorWindow flags={auditFlags} />
        <ServicesWindow services={services} />
        <RattingWindow ratting={ratting} />
        <PniWindow pni={pni} />
    </>
  );

  if (embedded) return adminWindows;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1.5">
      <StatusStrip>
        Administrative directorate · pending SRP {pendingSrp} · HR queue {pendingHr} · critical flags {criticalFlags}
      </StatusStrip>
      <KpiStrip>
        <KpiTile label="SRP queue" value={String(pendingSrp)} tone={pendingSrp ? "warn" : "ok"} />
        <KpiTile label="HR pending" value={String(pendingHr)} tone={pendingHr ? "warn" : "ok"} />
        <KpiTile label="Security flags" value={String(auditFlags.length)} tone={criticalFlags ? "danger" : "accent"} />
        <KpiTile label="Tax rules" value={String(taxRules.length)} />
      </KpiStrip>
      <DesktopSurface className="min-h-0 flex-1">{adminWindows}</DesktopSurface>
    </div>
  );
}
