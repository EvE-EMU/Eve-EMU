"use client";

import { useCallback, useEffect, useState } from "react";
import { characterPortraitUrl } from "@/lib/evetech";
import { formatEveTime } from "@/lib/eveTime";
import { fmtIskCompact, formatWalletDropFlag } from "@/lib/iskFormat";
import { useAuth } from "@/components/AuthProvider";
import { CharSheetOrgLink } from "@/components/tools/CharSheetOrgLink";
import { CharacterSheetAssets, type AssetLocation } from "@/components/tools/CharacterSheetAssets";
import { CharacterSheetClones, type CloneSnapshot } from "@/components/tools/CharacterSheetClones";
import { CharacterSheetContracts, type ContractRow } from "@/components/tools/CharacterSheetContracts";
import { CharacterSheetMail, type MailHeaderRow } from "@/components/tools/CharacterSheetMail";
import { CharacterSheetCombat, type CombatLogRow } from "@/components/tools/CharacterSheetCombat";
import { CharacterSheetHistory, type CorpHistoryRow } from "@/components/tools/CharacterSheetHistory";
import { CharacterSheetWallet, type WalletJournalRow } from "@/components/tools/CharacterSheetWallet";
import {
  CharacterSheetSkills,
  SkillLevelPipsCompact,
  type CharacterSkillRow,
  type SkillQueueRow,
} from "@/components/tools/CharacterSheetSkills";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";
import { PilotLookupPanel } from "@/components/tools/PilotLookupPanel";
import { RosterCombinedPanel } from "@/components/tools/RosterCombinedPanel";

export type CharacterSheet = {
  character_id: number;
  character_name: string;
  corporation_id?: number;
  corporation_name: string;
  alliance_id?: number | null;
  alliance_name?: string | null;
  wallet_balance_isk: string;
  skill_points: number;
  current_location?: string | null;
  main_system_id?: number | null;
  location_detail?: {
    solar_system_id?: number | null;
    system_name?: string | null;
    location_name?: string | null;
  } | null;
  skills_trained: number;
  last_sync_at: string | null;
  last_sync_eve?: string | null;
  next_sync_at?: string | null;
  next_sync_eve?: string | null;
  sync_interval_minutes?: number;
  scopes: string[];
  missing_scopes?: string[];
  sync_errors?: Record<string, string>;
  has_skills_access?: boolean;
  has_skill_queue_access?: boolean;
  scope_status?: { scope: string; label: string; granted: boolean }[];
  has_wallet_access?: boolean;
  has_assets_access?: boolean;
  has_location_access?: boolean;
  has_clones_access?: boolean;
  has_contracts_access?: boolean;
  has_mail_access?: boolean;
  has_killmails_access?: boolean;
  reauthorize_url?: string;
  skills: CharacterSkillRow[];
  skill_queue?: SkillQueueRow[];
  recent_skills?: CharacterSkillRow[];
  asset_locations?: AssetLocation[];
  clones?: CloneSnapshot;
  contracts?: ContractRow[];
  mail?: MailHeaderRow[];
  combat_log?: CombatLogRow[];
  corp_history?: CorpHistoryRow[];
  asset_groups: {
    location_flag: string;
    item_count: number;
    total_quantity: number;
    items: { type_id: number; type_name: string; quantity: number }[];
  }[];
  wallet_journal: WalletJournalRow[];
  flags: { flag_key: string; severity: string; detail: string }[];
  linked_characters: { character_id: number; character_name: string; is_main: boolean }[];
  online?: { online?: boolean; last_login?: string | null; last_logout?: string | null } | null;
  active_ship?: { ship_type_name?: string | null; ship_name?: string | null } | null;
  fatigue?: { jump_fatigue_expire_date?: string | null; last_jump_date?: string | null } | null;
  corp_roles?: { roles?: string[] } | null;
  corp_titles?: string[];
  standings?: { from_name?: string; from_type?: string; standing?: number }[];
  contacts?: { contact_name?: string; label?: string; standing?: number }[];
  eve_notifications?: { type?: string; timestamp?: string; is_read?: boolean }[];
  loyalty_points?: { corporation_name?: string; loyalty_points?: number }[];
  calendar_events?: { title?: string; event_date?: string; importance?: number }[];
  market_orders?: {
    order_id: number;
    type_name: string;
    is_buy_order: boolean;
    price: string;
    volume_remain: number;
    location_name: string;
  }[];
  view_mode: string;
  can_sync: boolean;
};

type TabId = "overview" | "skills" | "assets" | "wallet" | "clones" | "contracts" | "mail" | "combat" | "history" | "scopes";

function fmtIsk(value: string | number) {
  return fmtIskCompact(value);
}

function fmtDate(iso: string | null) {
  if (!iso) return "Never";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function ScopePrompt({
  sheet,
  filter,
}: {
  sheet: CharacterSheet;
  filter?: "wallet" | "assets" | "clones" | "contracts" | "mail" | "combat";
}) {
  const missing = sheet.missing_scopes ?? [];
  const relevant = (sheet.scope_status ?? []).filter((row) => {
    if (!filter) return !row.granted;
    if (filter === "wallet") return row.scope.includes("wallet") && !row.granted;
    if (filter === "assets") return row.scope.includes("assets") && !row.granted;
    if (filter === "clones") return row.scope.includes("clones") && !row.granted;
    if (filter === "contracts") return row.scope.includes("contracts") && !row.granted;
    if (filter === "mail") return row.scope.includes("mail") && !row.granted;
    if (filter === "combat") return row.scope.includes("killmails") && !row.granted;
    return false;
  });
  if (!missing.length && !relevant.length) return null;

  const loginUrl = sheet.reauthorize_url || "/api/auth/sso/login";
  return (
    <div className="eve-char-sheet-scope-prompt">
      <p className="eve-char-sheet-scope-title">EVE SSO permissions required</p>
      <p className="text-[var(--text-muted)]">
        Log in again and approve <strong>all</strong> requested scopes so EMUMS can read your{" "}
        {filter === "wallet" ? "wallet" : filter === "assets" ? "assets" : filter === "clones" ? "clone data" : filter === "contracts" ? "contracts" : filter === "mail" ? "mail" : filter === "combat" ? "killmails" : "character data"} from ESI.
      </p>
      <ul className="eve-char-sheet-scope-list">
        {(relevant.length ? relevant : (sheet.scope_status ?? []).filter((r) => !r.granted)).map((row) => (
          <li key={row.scope} className={row.granted ? "granted" : "missing"}>
            <code>{row.scope}</code>
            <span>{row.label}</span>
          </li>
        ))}
      </ul>
      <a href={loginUrl} className="eve-btn eve-btn-primary mt-2 inline-block">
        Grant all scopes via EVE SSO
      </a>
    </div>
  );
}

type CharacterSheetPanelProps = {
  characterId?: number;
  compact?: boolean;
};

export function CharacterSheetPanel({ characterId, compact = false }: CharacterSheetPanelProps) {
  const { session, loading: authLoading } = useAuth();
  const inspect = useCharSheetInspect();
  const altCount = session.alts?.length ?? 0;
  const showRosterDefault = altCount > 1 && !characterId;
  const [viewMode, setViewMode] = useState<"roster" | "single">(showRosterDefault ? "roster" : "single");
  const [activeId, setActiveId] = useState<number | undefined>(characterId);
  const [sheet, setSheet] = useState<CharacterSheet | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [loading, setLoading] = useState(!showRosterDefault);
  const [error, setError] = useState<string | null>(null);

  const loadSheet = useCallback(async (id?: number) => {
    setLoading(true);
    setError(null);
    const url = id ? `/api/audit/characters/${id}` : "/api/audit/me";
    const res = await fetch(url, { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) {
      setSheet(null);
      setError(res.status === 401 ? "Log in with EVE SSO to view your character sheet." : "Unable to load character sheet.");
      setLoading(false);
      return;
    }
    setSheet((await res.json()) as CharacterSheet);
    setLoading(false);
  }, []);

  useEffect(() => {
    setActiveId(characterId);
  }, [characterId]);

  useEffect(() => {
    if (authLoading) return;
    if (characterId) {
      setViewMode("single");
      setActiveId(characterId);
      return;
    }
    if (!session.authenticated) {
      setViewMode("single");
      setLoading(false);
      setSheet(null);
      setError("Log in with EVE SSO to view your character sheet.");
      return;
    }
    if (viewMode === "roster") {
      setLoading(false);
      setSheet(null);
      setError(null);
      return;
    }
    const targetId = activeId ?? session.character_id ?? undefined;
    void loadSheet(targetId);
  }, [authLoading, activeId, characterId, session.authenticated, session.character_id, viewMode, loadSheet]);

  useEffect(() => {
    const onSwitch = () => {
      if (altCount > 1 && !characterId) {
        setViewMode("roster");
        setActiveId(undefined);
      } else {
        setActiveId(undefined);
        void loadSheet(session.character_id ?? undefined);
      }
    };
    window.addEventListener("emums:character-switch", onSwitch);
    return () => window.removeEventListener("emums:character-switch", onSwitch);
  }, [loadSheet, session.character_id, altCount, characterId]);

  useEffect(() => {
    const onInspect = (ev: Event) => {
      const cid = (ev as CustomEvent<{ character_id?: number }>).detail?.character_id;
      if (!cid || characterId) return;
      setViewMode("single");
      setActiveId(cid);
      setLoading(true);
      void loadSheet(cid);
    };
    window.addEventListener("emums:inspect-character", onInspect);
    return () => window.removeEventListener("emums:inspect-character", onInspect);
  }, [characterId, loadSheet]);

  if (viewMode === "roster" && session.authenticated && !characterId) {
    return (
      <div className={`eve-char-sheet ${compact ? "eve-char-sheet--compact" : ""}`}>
        {session.hr_lookup ? (
          <PilotLookupPanel
            onSelect={(id) => {
              setViewMode("single");
              setActiveId(id);
              setLoading(true);
            }}
          />
        ) : null}
        <RosterCombinedPanel
          onSelectCharacter={(id) => {
            setViewMode("single");
            setActiveId(id);
            setLoading(true);
          }}
        />
      </div>
    );
  }

  const recentSkills = sheet?.recent_skills ?? [];

  if (loading) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">Loading character sheet…</p>;
  }

  if (error || !sheet) {
    return (
      <div className="p-3 text-[11px]">
        <p className="text-[var(--text-muted)]">{error ?? "No character data."}</p>
        {!session.authenticated ? (
          <a href={session.login_url || "/api/auth/sso/login"} className="eve-btn eve-btn-primary mt-2 inline-block">
            Log in with EVE SSO
          </a>
        ) : null}
      </div>
    );
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "skills", label: `Skills (${sheet.skills_trained})` },
    { id: "assets", label: "Assets" },
    { id: "wallet", label: "Wallet" },
    { id: "clones", label: "Clones" },
    { id: "contracts", label: `Contracts (${sheet.contracts?.length ?? 0})` },
    { id: "mail", label: `Mail (${sheet.mail?.length ?? 0})` },
    { id: "combat", label: `Combat (${sheet.combat_log?.length ?? 0})` },
    { id: "history", label: `History (${sheet.corp_history?.length ?? 0})` },
    { id: "scopes", label: "Scopes" },
  ];

  return (
    <div className={`eve-char-sheet ${compact ? "eve-char-sheet--compact" : ""}`}>
      {altCount > 1 && !characterId ? (
        <button
          type="button"
          className="eve-roster-back-btn mb-2"
          onClick={() => {
            setViewMode("roster");
            setActiveId(undefined);
          }}
        >
          ← All characters ({altCount})
        </button>
      ) : null}
      {session.hr_lookup && !characterId && viewMode === "single" ? (
        <PilotLookupPanel
          onSelect={(id) => {
            setViewMode("single");
            setActiveId(id);
            setLoading(true);
          }}
        />
      ) : null}
      <div className="eve-char-sheet-header">
        <div className="eve-char-sheet-portrait-wrap">
          <img
            src={characterPortraitUrl(sheet.character_id, 256)}
            alt=""
            width={compact ? 72 : 96}
            height={compact ? 72 : 96}
            className="eve-char-sheet-portrait"
          />
        </div>
        <div className="eve-char-sheet-identity">
          <h2 className="eve-char-sheet-name">{sheet.character_name}</h2>
          <CharSheetOrgLink
            corpId={sheet.corporation_id}
            corpName={sheet.corporation_name}
            allianceId={sheet.alliance_id}
            allianceName={sheet.alliance_name}
          />
          <div className="eve-char-sheet-stats">
            <div className="eve-char-sheet-stat">
              <span className="label">Skill points</span>
              <span className="value">{sheet.skill_points.toLocaleString()}</span>
            </div>
            <div className="eve-char-sheet-stat">
              <span className="label">Wallet</span>
              <span className="value">{fmtIsk(sheet.wallet_balance_isk)} ISK</span>
            </div>
            <div className="eve-char-sheet-stat">
              <span className="label">Location</span>
              <span className="value">
                {sheet.main_system_id && inspect?.openSystemDetail ? (
                  <button
                    type="button"
                    className="eve-char-sheet-location-link"
                    title="Open system details"
                    onClick={() =>
                      inspect.openSystemDetail(
                        sheet.main_system_id!,
                        sheet.location_detail?.system_name || sheet.current_location || undefined
                      )
                    }
                  >
                    {sheet.current_location || sheet.location_detail?.system_name || "—"}
                  </button>
                ) : (
                  sheet.current_location || "—"
                )}
              </span>
            </div>
            <div className="eve-char-sheet-stat">
              <span className="label">Last sync (EVE)</span>
              <span className="value">{sheet.last_sync_eve || formatEveTime(sheet.last_sync_at)}</span>
            </div>
            <div className="eve-char-sheet-stat">
              <span className="label">Next sync (EVE)</span>
              <span className="value">{sheet.next_sync_eve || "—"}</span>
            </div>
          </div>
          <div className="eve-char-sheet-actions">
            {altCount > 1 && !characterId ? (
              <button type="button" className="eve-btn-sm" onClick={() => setViewMode("roster")}>
                View all {altCount} characters
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {sheet.flags.length ? (
        <div className="eve-char-sheet-flags">
          {sheet.flags.map((f) => (
            <div key={f.flag_key} className={f.severity === "critical" ? "critical" : "warn"}>
              {f.flag_key === "wallet_drop" ? formatWalletDropFlag(f.detail) : f.detail}
            </div>
          ))}
        </div>
      ) : null}

      {sheet.missing_scopes?.length ? (
        <ScopePrompt sheet={sheet} />
      ) : null}

      <div className="eve-char-sheet-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="eve-char-sheet-body eve-scroll">
        {tab === "overview" ? (
          <div className="eve-char-sheet-overview">
            <section>
              <h3>Account</h3>
              <dl>
                <dt>Character ID</dt>
                <dd>{sheet.character_id}</dd>
                <dt>Skills trained</dt>
                <dd>{sheet.skills_trained}</dd>
                <dt>ESI scopes</dt>
                <dd>{sheet.scopes.length || "—"}</dd>
              </dl>
            </section>
            <section>
              <h3>Live status</h3>
              <dl>
                <dt>Online</dt>
                <dd>
                  {sheet.online
                    ? sheet.online.online
                      ? "Online now"
                      : sheet.online.last_logout
                        ? `Offline (last logout ${fmtDate(sheet.online.last_logout)})`
                        : "Offline"
                    : "—"}
                </dd>
                <dt>Active ship</dt>
                <dd>
                  {sheet.active_ship?.ship_type_name
                    ? `${sheet.active_ship.ship_name ? `${sheet.active_ship.ship_name} — ` : ""}${sheet.active_ship.ship_type_name}`
                    : "—"}
                </dd>
                <dt>Jump fatigue</dt>
                <dd>
                  {sheet.fatigue?.jump_fatigue_expire_date
                    ? fmtDate(sheet.fatigue.jump_fatigue_expire_date)
                    : "Clear"}
                </dd>
                <dt>Corp roles</dt>
                <dd>{sheet.corp_roles?.roles?.length ? sheet.corp_roles.roles.join(", ") : "—"}</dd>
                <dt>Corp titles</dt>
                <dd>{sheet.corp_titles?.length ? sheet.corp_titles.join(", ") : "—"}</dd>
                <dt>Market orders</dt>
                <dd>{sheet.market_orders?.length ?? 0}</dd>
                <dt>Contacts</dt>
                <dd>{sheet.contacts?.length ?? 0}</dd>
                <dt>Loyalty points</dt>
                <dd>
                  {sheet.loyalty_points?.length
                    ? sheet.loyalty_points
                        .slice(0, 3)
                        .map((r) => `${r.corporation_name ?? "Corp"}: ${(r.loyalty_points ?? 0).toLocaleString()} LP`)
                        .join(" · ")
                    : "—"}
                </dd>
              </dl>
            </section>
            <section>
              <h3>Recent skills</h3>
              <ul className="eve-char-sheet-top-skills">
                {recentSkills.length ? (
                  recentSkills.map((s) => (
                    <li key={s.skill_type_id}>
                      <EveTypeIcon typeId={s.skill_type_id} size={20} preferRender categoryName="Skill" />
                      <span className="name">{s.skill_name}</span>
                      <SkillLevelPipsCompact
                        trained={s.trained_level}
                        active={s.active_level ?? s.trained_level}
                        isTraining={s.is_training}
                      />
                    </li>
                  ))
                ) : (
                  <li className="text-[var(--text-muted)]">
                    {!sheet.has_skill_queue_access
                      ? "Skill queue scope missing — re-login via SSO to grant esi-skills.read_skillqueue.v1."
                      : sheet.sync_errors?.skill_queue || sheet.sync_errors?.skills
                        ? sheet.sync_errors.skill_queue || sheet.sync_errors.skills
                        : "No skill queue — empty queue or awaiting next sync."}
                  </li>
                )}
              </ul>
            </section>
            <section>
              <h3>Recent wallet activity</h3>
              {sheet.wallet_journal.length ? (
                <table className="eve-table text-[10px]">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.wallet_journal.slice(0, 6).map((j, i) => (
                      <tr key={i}>
                        <td>{fmtDate(j.recorded_at)}</td>
                        <td>{j.ref_type}</td>
                        <td className={Number(j.amount) >= 0 ? "text-[var(--ok)]" : "text-[var(--danger)]"}>
                          {fmtIsk(j.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-[var(--text-muted)]">No wallet journal entries synced yet.</p>
              )}
            </section>
          </div>
        ) : null}

        {tab === "skills" ? (
          <CharacterSheetSkills skills={sheet.skills} skillQueue={sheet.skill_queue ?? []} />
        ) : null}

        {tab === "assets" ? (
          <div className="space-y-3">
            {!sheet.has_assets_access ? <ScopePrompt sheet={sheet} filter="assets" /> : null}
            {sheet.has_assets_access ? (
              <CharacterSheetAssets locations={sheet.asset_locations ?? []} />
            ) : null}
          </div>
        ) : null}

        {tab === "wallet" ? (
          <>
            {!sheet.has_wallet_access ? <ScopePrompt sheet={sheet} filter="wallet" /> : null}
            {sheet.has_wallet_access ? <CharacterSheetWallet journal={sheet.wallet_journal} /> : null}
          </>
        ) : null}

        {tab === "clones" ? (
          <div className="space-y-3">
            {!sheet.has_clones_access ? <ScopePrompt sheet={sheet} filter="clones" /> : null}
            {sheet.has_clones_access ? (
              <CharacterSheetClones clones={sheet.clones ?? {}} />
            ) : null}
          </div>
        ) : null}

        {tab === "contracts" ? (
          <div className="space-y-3">
            {!sheet.has_contracts_access ? <ScopePrompt sheet={sheet} filter="contracts" /> : null}
            {sheet.has_contracts_access ? (
              <CharacterSheetContracts contracts={sheet.contracts ?? []} />
            ) : null}
          </div>
        ) : null}

        {tab === "mail" ? (
          <div className="space-y-3">
            {!sheet.has_mail_access ? <ScopePrompt sheet={sheet} filter="mail" /> : null}
            {sheet.has_mail_access ? (
              <CharacterSheetMail characterId={sheet.character_id} mail={sheet.mail ?? []} />
            ) : null}
          </div>
        ) : null}

        {tab === "combat" ? (
          <div className="space-y-3">
            {!sheet.has_killmails_access ? <ScopePrompt sheet={sheet} filter="combat" /> : null}
            {sheet.has_killmails_access ? (
              <CharacterSheetCombat combatLog={sheet.combat_log ?? []} />
            ) : null}
          </div>
        ) : null}

        {tab === "history" ? (
          <div className="space-y-3">
            <CharacterSheetHistory history={sheet.corp_history ?? []} />
          </div>
        ) : null}

        {tab === "scopes" ? (
          <div className="space-y-3">
            {sheet.missing_scopes?.length ? <ScopePrompt sheet={sheet} /> : null}
            <table className="eve-table w-full text-[10px]">
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>Description</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(sheet.scope_status ?? sheet.scopes.map((scope) => ({ scope, label: scope, granted: true }))).map(
                  (row) => (
                    <tr key={row.scope}>
                      <td>
                        <code>{row.scope}</code>
                      </td>
                      <td>{row.label}</td>
                      <td className={row.granted ? "text-[var(--ok)]" : "text-[var(--warn)]"}>
                        {row.granted ? "Granted" : "Missing — re-login required"}
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}
