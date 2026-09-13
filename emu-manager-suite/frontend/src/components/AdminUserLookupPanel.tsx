"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { EveWindow, SectionHead, StatusStrip } from "@/components/ui";
import { characterPortraitUrl } from "@/lib/evetech";
import {
  assignAdminGroup,
  fetchAdminUser,
  fetchIdentityGroups,
  revokeAdminGroup,
  searchAdminUsers,
  type AdminUserDetail,
  type AdminUserHit,
  type IdentityGroup,
} from "@/lib/identityAdmin";
import { useAuth } from "@/components/AuthProvider";
import { isAdministrator } from "@/lib/permissions";

export function AdminUserLookupPanel() {
  const { session, refresh } = useAuth();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<AdminUserHit[]>([]);
  const [groups, setGroups] = useState<IdentityGroup[]>([]);
  const [selected, setSelected] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const admin = isAdministrator(session);

  useEffect(() => {
    if (!admin) return;
    void fetchIdentityGroups().then(setGroups);
  }, [admin]);

  const loadUser = useCallback(async (characterId: number) => {
    setLoading(true);
    setError("");
    try {
      setSelected(await fetchAdminUser(characterId));
    } catch {
      setError("Could not load user details.");
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!admin || query.trim().length < 2) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      setLoading(true);
      searchAdminUsers(query.trim())
        .then(setHits)
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 260);
    return () => window.clearTimeout(handle);
  }, [admin, query]);

  const toggleGroup = async (groupId: number, active: boolean) => {
    if (!selected) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (active) {
        await revokeAdminGroup(selected.character_id, groupId);
        setMessage("Group revoked.");
      } else {
        await assignAdminGroup(selected.character_id, groupId);
        setMessage("Group assigned.");
      }
      await loadUser(selected.character_id);
      if (selected.character_id === session.character_id) {
        await refresh();
      }
    } catch {
      setError("Permission update failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!admin) {
    return (
      <EveWindow id="admin-users" title="Users & Permissions" defaultX={4} defaultY={300} defaultWidth={480} defaultHeight={420}>
        <p className="text-[11px] text-[var(--text-muted)]">Administrator access required.</p>
      </EveWindow>
    );
  }

  const activeGroupIds = new Set(
    (selected?.group_memberships ?? [])
      .filter((m) => m.status === "active")
      .map((m) => m.group_id)
  );

  return (
    <EveWindow id="admin-users" title="Users & Permissions" defaultX={4} defaultY={300} defaultWidth={520} defaultHeight={460}>
      <StatusStrip>Search pilots, review coalition groups, and grant administrator access</StatusStrip>
      <div className="flex flex-col gap-2 h-full min-h-0">
        <input
          className="eve-input"
          placeholder="Search character name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {loading && !selected ? <p className="text-[10px] text-[var(--text-muted)]">Searching…</p> : null}
        {error ? <p className="text-[10px] text-[var(--danger)]">{error}</p> : null}
        {message ? <p className="text-[10px] text-[var(--ok)]">{message}</p> : null}

        {!selected && hits.length ? (
          <ul className="space-y-1 overflow-auto flex-1 min-h-0">
            {hits.map((hit) => (
              <li key={hit.character_id}>
                <button
                  type="button"
                  className="eve-wiki-result-link flex items-center gap-2 w-full text-left"
                  onClick={() => void loadUser(hit.character_id)}
                >
                  <img src={characterPortraitUrl(hit.character_id, 32)} alt="" width={24} height={24} />
                  <span>
                    {hit.character_name}
                    <span className="text-[var(--text-muted)] ml-1">{hit.corporation_name}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {selected ? (
          <div className="overflow-auto flex-1 min-h-0 space-y-3">
            <div className="flex items-center gap-2">
              <img src={characterPortraitUrl(selected.character_id, 64)} alt="" width={40} height={40} />
              <div>
                <SectionHead>{selected.character_name}</SectionHead>
                <p className="text-[10px] text-[var(--text-muted)]">
                  {selected.corporation_name ?? "Unknown corp"} · State: {selected.state ?? "—"}
                </p>
                <p className="text-[10px] text-[var(--text-muted)]">
                  Permissions: {selected.permissions.join(", ") || "—"}
                </p>
              </div>
            </div>

            <section>
              <SectionHead>Coalition groups</SectionHead>
              <table className="eve-table text-[10px] w-full">
                <thead>
                  <tr>
                    <th>Group</th>
                    <th>Permissions</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => {
                    const active = activeGroupIds.has(group.id);
                    return (
                      <tr key={group.id}>
                        <td>
                          {group.name}
                          {group.name === "Directors" ? (
                            <span className="text-[var(--accent)] ml-1">(admin)</span>
                          ) : null}
                        </td>
                        <td className="text-[var(--text-muted)]">{group.permissions.join(", ") || "—"}</td>
                        <td className="text-right">
                          <button
                            type="button"
                            className={clsx("eve-btn-sm", active && "eve-btn-primary")}
                            disabled={busy}
                            onClick={() => void toggleGroup(group.id, active)}
                          >
                            {active ? "Revoke" : "Grant"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>

            <button type="button" className="eve-btn-sm" onClick={() => setSelected(null)}>
              Back to search
            </button>
          </div>
        ) : null}
      </div>
    </EveWindow>
  );
}
