/** Client helpers for directorate administration actions. */

export type InfrastructureStatus = {
  checked_at: string;
  environment: string;
  redis: { reachable: boolean; connected_clients?: number; used_memory_human?: string; error?: string };
  celery: {
    workers_online: number;
    worker_names: string[];
    active_task_count: number;
    active_by_worker: Record<string, { name: string; id: string }[]>;
    scheduled_count: number;
    beat_schedule: { name: string; task: string; schedule: string }[];
  };
};

export async function fetchInfrastructure(): Promise<InfrastructureStatus> {
  const res = await fetch("/api/admin/infrastructure", { cache: "no-store" });
  if (!res.ok) throw new Error("Infrastructure telemetry unavailable");
  return res.json();
}

export async function patchSrpStatus(id: number, status: string) {
  const res = await fetch(`/api/admin/srp/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("SRP update failed");
  return res.json();
}

export async function patchHrLeaveStatus(id: number, status: string) {
  const res = await fetch(`/api/admin/hr/leaves/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Leave update failed");
  return res.json();
}

export async function patchTaxRule(
  ruleId: number,
  body: { r16_pct: number; r32_pct: number; r64_pct: number }
) {
  const res = await fetch(`/api/admin/tax-rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Tax rule update failed");
  return res.json();
}

export async function setServiceLock(locked: boolean, reason = "") {
  const res = await fetch("/api/admin/services/lock", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locked, reason }),
  });
  if (!res.ok) throw new Error("Service lock failed");
  return res.json();
}

export async function fetchHrBlacklist() {
  const res = await fetch("/api/admin/hr/blacklist", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export async function fetchHrFlags() {
  const res = await fetch("/api/admin/hr/flags", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export type HrRoleTitleRow = {
  id: number;
  corporation_id: number;
  title_id: number;
  title_name: string;
  description: string;
  active: boolean;
};

export async function fetchHrRoleTitles(): Promise<HrRoleTitleRow[]> {
  const res = await fetch("/api/admin/hr/role-titles", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export async function createHrRoleTitle(body: {
  corporation_id: number;
  title_id: number;
  title_name: string;
  description?: string;
}) {
  const res = await fetch("/api/admin/hr/role-titles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to add HR role title");
  return res.json();
}

export type HrAuditRuleRow = {
  id: number;
  rule_key: string;
  name: string;
  description: string;
  enabled: boolean;
  severity: "warn" | "critical";
  rule_type:
    | "mail_subject"
    | "wallet_ref_type"
    | "blacklist_contact"
    | "wallet_drop"
    | "interaction_threshold";
  match_json: string;
  webhook_url: string;
  notify_in_app: boolean;
  cooldown_hours: number;
};

export async function fetchHrAuditRules(): Promise<HrAuditRuleRow[]> {
  const res = await fetch("/api/admin/hr/audit-rules", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export async function createHrAuditRule(body: Omit<HrAuditRuleRow, "id">) {
  const res = await fetch("/api/admin/hr/audit-rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create audit rule");
  return res.json();
}

export async function patchHrAuditRule(
  id: number,
  body: Partial<Omit<HrAuditRuleRow, "id" | "rule_key" | "rule_type">>
) {
  const res = await fetch(`/api/admin/hr/audit-rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update audit rule");
  return res.json();
}

export async function deleteHrAuditRule(id: number) {
  const res = await fetch(`/api/admin/hr/audit-rules/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete audit rule");
  return res.json();
}

export type SrpRateRuleRow = {
  id: number;
  label: string;
  ship_type_id: number;
  ship_type_name: string;
  doctrine_slug: string;
  base_srp_isk: string;
  max_percent: string | null;
  doctrine_multiplier: string;
  meta_multiplier: string;
  shitfit_multiplier: string;
  allow_shitfit: boolean;
  enabled: boolean;
  priority: number;
};

export async function fetchSrpRateRules(): Promise<SrpRateRuleRow[]> {
  const res = await fetch("/api/admin/srp/rules", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export async function createSrpRateRule(body: Omit<SrpRateRuleRow, "id">) {
  const res = await fetch("/api/admin/srp/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create SRP rate");
  return res.json();
}

export async function patchSrpRateRule(id: number, body: Partial<Omit<SrpRateRuleRow, "id">>) {
  const res = await fetch(`/api/admin/srp/rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update SRP rate");
  return res.json();
}

export async function deleteSrpRateRule(id: number) {
  const res = await fetch(`/api/admin/srp/rules/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete SRP rate");
  return res.json();
}

export type BuildStructureRow = {
  id: number;
  structure_id: number;
  structure_name: string;
  system_name: string;
  location_label: string;
  material_bonus_pct: number;
  time_bonus_pct: number;
  tax_pct: number;
  has_manufacturing: boolean;
};

export async function fetchBuildStructures(): Promise<BuildStructureRow[]> {
  const res = await fetch("/api/admin/build-structures", { cache: "no-store" });
  return res.ok ? res.json() : [];
}

export async function createBuildStructure(body: Omit<BuildStructureRow, "id">) {
  const res = await fetch("/api/admin/build-structures", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create build structure");
  return res.json();
}

export async function patchBuildStructure(id: number, body: Partial<Omit<BuildStructureRow, "id" | "structure_id">>) {
  const res = await fetch(`/api/admin/build-structures/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update build structure");
  return res.json();
}

export async function deleteBuildStructure(id: number) {
  const res = await fetch(`/api/admin/build-structures/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete build structure");
  return res.json();
}
