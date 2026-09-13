"use client";

import { useEffect, useState } from "react";
import { EveWindow, SectionHead, StatusStrip } from "@/components/ui";
import { WindowDesktop } from "@/components/WindowManager";

type State = { id: number; name: string; priority_weight: number; color: string; description?: string };
type Group = {
  id: number;
  name: string;
  description: string;
  is_open: boolean;
  discord_role_id: string;
  permissions: string[];
};
type StateRule = {
  id: number;
  state_id: number;
  allowed_alliance_ids: number[];
  allowed_corporation_ids: number[];
  priority: number;
};

const COMMON_PERMS = [
  "tools.public",
  "tools.guest",
  "tools.friendly",
  "tools.blue",
  "tools.member",
  "industrial.storefront",
  "moons.view",
  "hr.view",
  "hr.manage",
  "srp.submit",
  "intel.read",
  "map.bookmarks",
  "audit.view",
  "settings.admin",
  "admission.review",
  "director",
  "admin",
];

export function IdentityAdminPanel({
  windowId = "identity-rbac",
  defaultX = 40,
  defaultY = 40,
  defaultWidth = 720,
  defaultHeight = 560,
}: {
  windowId?: string;
  defaultX?: number;
  defaultY?: number;
  defaultWidth?: number;
  defaultHeight?: number;
}) {
  const [states, setStates] = useState<State[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [rules, setRules] = useState<StateRule[]>([]);
  const [allPerms, setAllPerms] = useState<string[]>(COMMON_PERMS);
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [guildId, setGuildId] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);
  const [selectedRule, setSelectedRule] = useState<number | null>(null);
  const [corpIdsText, setCorpIdsText] = useState("");
  const [alliIdsText, setAlliIdsText] = useState("");
  const [assignCharId, setAssignCharId] = useState("");
  const [assignCharName, setAssignCharName] = useState("");
  const [newGroupName, setNewGroupName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const reload = async () => {
    const [s, g, r, c, p] = await Promise.all([
      fetch("/api/identity/states").then((x) => (x.ok ? x.json() : [])),
      fetch("/api/identity/groups").then((x) => (x.ok ? x.json() : [])),
      fetch("/api/identity/state-rules").then((x) => (x.ok ? x.json() : [])),
      fetch("/api/identity/service-sync/config").then((x) => (x.ok ? x.json() : {})),
      fetch("/api/people/permissions/catalog").then((x) => (x.ok ? x.json() : null)),
    ]);
    setStates(s);
    setGroups(g);
    setRules(r);
    const cfg = c as { enabled?: boolean; discord_guild_id?: string };
    setSyncEnabled(Boolean(cfg.enabled));
    setGuildId(cfg.discord_guild_id ?? "");
    if (p?.all_permissions?.length) setAllPerms(p.all_permissions);
  };

  useEffect(() => {
    void reload();
  }, []);

  useEffect(() => {
    const rule = rules.find((x) => x.id === selectedRule);
    if (!rule) {
      setCorpIdsText("");
      setAlliIdsText("");
      return;
    }
    setCorpIdsText(rule.allowed_corporation_ids.join(", "));
    setAlliIdsText(rule.allowed_alliance_ids.join(", "));
  }, [selectedRule, rules]);

  const selectedGroupObj = groups.find((g) => g.id === selectedGroup) || null;

  const togglePerm = async (perm: string) => {
    if (!selectedGroupObj) return;
    const perms = new Set(selectedGroupObj.permissions);
    if (perms.has(perm)) perms.delete(perm);
    else perms.add(perm);
    const res = await fetch(`/api/identity/groups/${selectedGroupObj.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ permissions: [...perms] }),
    });
    if (!res.ok) {
      setError("Failed to update permissions (need administrator).");
      return;
    }
    setMessage(`Updated permissions for ${selectedGroupObj.name}`);
    await reload();
  };

  const saveRule = async () => {
    if (!selectedRule) return;
    const corps = corpIdsText
      .split(/[,\s]+/)
      .map((x) => parseInt(x, 10))
      .filter((n) => n > 0);
    const allis = alliIdsText
      .split(/[,\s]+/)
      .map((x) => parseInt(x, 10))
      .filter((n) => n > 0);
    const res = await fetch(`/api/identity/state-rules/${selectedRule}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        allowed_corporation_ids: corps,
        allowed_alliance_ids: allis,
      }),
    });
    if (!res.ok) {
      setError("Failed to update state rule.");
      return;
    }
    setMessage("State rule saved.");
    await reload();
  };

  const createGroup = async () => {
    if (!newGroupName.trim()) return;
    const res = await fetch("/api/identity/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newGroupName.trim(), permissions: [] }),
    });
    if (!res.ok) {
      setError("Failed to create group.");
      return;
    }
    setNewGroupName("");
    setMessage("Group created.");
    await reload();
  };

  const assignMember = async () => {
    if (!selectedGroup || !assignCharId) return;
    const res = await fetch(`/api/identity/groups/${selectedGroup}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        character_id: parseInt(assignCharId, 10),
        character_name: assignCharName,
        status: "active",
      }),
    });
    if (!res.ok) {
      setError("Assign failed (administrator required).");
      return;
    }
    setMessage("Member assigned.");
    setAssignCharId("");
    setAssignCharName("");
  };

  const saveSync = async () => {
    await fetch("/api/identity/service-sync/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: syncEnabled, discord_guild_id: guildId }),
    });
    setMessage("Service sync config saved.");
  };

  const stateName = (id: number) => states.find((s) => s.id === id)?.name || `#${id}`;

  return (
    <EveWindow
      id={windowId}
      title="Permissions Manager"
      defaultWidth={defaultWidth}
      defaultHeight={defaultHeight}
      defaultX={defaultX}
      defaultY={defaultY}
    >
      <div className="space-y-3 text-[11px] min-h-0 h-full overflow-auto">
        <StatusStrip>States, rules, groups, and Discord sync — edit permissions live</StatusStrip>
        {message ? <p className="text-[var(--ok)]">{message}</p> : null}
        {error ? <p className="text-[var(--danger)]">{error}</p> : null}

        <section>
          <SectionHead>States</SectionHead>
          <table className="eve-table w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th>Priority</th>
                <th>Color</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {states.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.priority_weight}</td>
                  <td>
                    <span className="eve-tag">{s.color}</span>
                  </td>
                  <td className="text-[var(--text-muted)]">{s.description || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <SectionHead>State rules (corp / alliance → state)</SectionHead>
          <div className="flex flex-wrap gap-2 mb-2">
            <select
              className="eve-select"
              value={selectedRule ?? ""}
              onChange={(e) => setSelectedRule(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Select rule…</option>
              {rules.map((r) => (
                <option key={r.id} value={r.id}>
                  {stateName(r.state_id)} (#{r.id})
                </option>
              ))}
            </select>
            {selectedRule ? (
              <>
                <input
                  className="eve-input flex-1 min-w-[120px]"
                  placeholder="Corp IDs (comma-separated)"
                  value={corpIdsText}
                  onChange={(e) => setCorpIdsText(e.target.value)}
                />
                <input
                  className="eve-input flex-1 min-w-[120px]"
                  placeholder="Alliance IDs"
                  value={alliIdsText}
                  onChange={(e) => setAlliIdsText(e.target.value)}
                />
                <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void saveRule()}>
                  Save rule
                </button>
              </>
            ) : null}
          </div>
          {rules.map((r) => (
            <p key={r.id} className="text-[var(--text-muted)]">
              <strong>{stateName(r.state_id)}</strong>: corps [{r.allowed_corporation_ids.join(", ") || "—"}] ·
              alliances [{r.allowed_alliance_ids.join(", ") || "—"}]
            </p>
          ))}
        </section>

        <section>
          <SectionHead>Groups & permissions</SectionHead>
          <div className="flex gap-2 mb-2">
            <input
              className="eve-input flex-1"
              placeholder="New group name"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
            />
            <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => void createGroup()}>
              Create group
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <table className="eve-table w-full">
                <thead>
                  <tr>
                    <th>Group</th>
                    <th>Open</th>
                    <th>Perms</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr
                      key={g.id}
                      className={selectedGroup === g.id ? "eve-row-selected" : "cursor-pointer"}
                      onClick={() => setSelectedGroup(g.id)}
                    >
                      <td>{g.name}</td>
                      <td>{g.is_open ? "Yes" : "Managed"}</td>
                      <td>{g.permissions.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selectedGroup ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  <input
                    className="eve-input w-28"
                    placeholder="Char ID"
                    value={assignCharId}
                    onChange={(e) => setAssignCharId(e.target.value)}
                  />
                  <input
                    className="eve-input flex-1"
                    placeholder="Character name"
                    value={assignCharName}
                    onChange={(e) => setAssignCharName(e.target.value)}
                  />
                  <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void assignMember()}>
                    Assign
                  </button>
                </div>
              ) : null}
            </div>
            <div className="border border-[var(--edge-dim)] p-2 max-h-56 overflow-auto">
              <div className="mb-1 text-[var(--text-muted)]">
                {selectedGroupObj ? `Permissions: ${selectedGroupObj.name}` : "Select a group"}
              </div>
              {selectedGroupObj
                ? allPerms.map((perm) => (
                    <label key={perm} className="flex items-center gap-2 py-0.5">
                      <input
                        type="checkbox"
                        checked={selectedGroupObj.permissions.includes(perm)}
                        onChange={() => void togglePerm(perm)}
                      />
                      <span className="font-mono text-[10px]">{perm}</span>
                    </label>
                  ))
                : null}
            </div>
          </div>
        </section>

        <section>
          <SectionHead>Service sync</SectionHead>
          <label className="flex items-center gap-2 mb-2">
            <input type="checkbox" checked={syncEnabled} onChange={(e) => setSyncEnabled(e.target.checked)} />
            Enable Discord / Mumble sync
          </label>
          <input
            className="eve-input w-full mb-2"
            placeholder="Discord guild ID"
            value={guildId}
            onChange={(e) => setGuildId(e.target.value)}
          />
          <button type="button" className="eve-btn-sm" onClick={() => void saveSync()}>
            Save sync config
          </button>
        </section>
      </div>
    </EveWindow>
  );
}

export function IdentitySettingsSection() {
  return (
    <WindowDesktop>
      <IdentityAdminPanel />
    </WindowDesktop>
  );
}
