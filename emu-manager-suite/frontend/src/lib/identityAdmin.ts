export type AdminUserHit = {
  character_id: number;
  character_name: string;
  corporation_name: string;
  alliance_name: string;
};

export type AdminGroupMembership = {
  join_id: number;
  group_id: number;
  group_name: string;
  status: string;
  permissions: string[];
  is_open: boolean;
};

export type AdminUserDetail = {
  character_id: number;
  character_name: string;
  corporation_name: string | null;
  alliance_name: string | null;
  registered: boolean;
  state: string | null;
  groups: string[];
  permissions: string[];
  group_memberships: AdminGroupMembership[];
};

export type IdentityGroup = {
  id: number;
  name: string;
  description: string;
  is_open: boolean;
  permissions: string[];
};

export async function searchAdminUsers(q: string, limit = 20): Promise<AdminUserHit[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const res = await fetch(`/api/identity/admin/users/search?${params}`, {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("User search failed");
  return res.json();
}

export async function fetchAdminUser(characterId: number): Promise<AdminUserDetail> {
  const res = await fetch(`/api/identity/admin/users/${characterId}`, {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("User lookup failed");
  return res.json();
}

export async function assignAdminGroup(characterId: number, groupId: number): Promise<void> {
  const res = await fetch(`/api/identity/admin/users/${characterId}/groups/${groupId}`, {
    method: "POST",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("Could not assign group");
}

export async function revokeAdminGroup(characterId: number, groupId: number): Promise<void> {
  const res = await fetch(`/api/identity/admin/users/${characterId}/groups/${groupId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("Could not revoke group");
}

export async function fetchIdentityGroups(): Promise<IdentityGroup[]> {
  const res = await fetch("/api/identity/groups", { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}
