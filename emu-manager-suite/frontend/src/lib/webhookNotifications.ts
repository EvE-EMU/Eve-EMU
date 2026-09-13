/** Client helpers for user webhook notification rules. */

export type WebhookEventDef = {
  event_type: string;
  label: string;
  description: string;
  match_fields: string[];
};

export type WebhookDeliveryMode = {
  id: string;
  label: string;
  seconds: number;
};

export type WebhookRule = {
  id: number;
  name: string;
  description: string;
  enabled: boolean;
  event_type: string;
  match_json: string;
  webhook_url: string;
  notify_in_app: boolean;
  delivery_mode: string;
  all_characters: boolean;
  target_character_id: number | null;
  last_digest_at: string | null;
  created_at: string | null;
};

export type WebhookDelivery = {
  id: number;
  rule_id: number;
  character_id: number;
  delivery_mode: string;
  event_count: number;
  webhook_status: string;
  detail: string;
  created_at: string | null;
};

export async function fetchWebhookCatalog(): Promise<{
  events: WebhookEventDef[];
  delivery_modes: WebhookDeliveryMode[];
}> {
  const res = await fetch("/api/webhook-notifications/catalog", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load notification catalog");
  return res.json();
}

export async function fetchWebhookRules(): Promise<WebhookRule[]> {
  const res = await fetch("/api/webhook-notifications/rules", {
    cache: "no-store",
    credentials: "same-origin",
  });
  return res.ok ? res.json() : [];
}

export async function createWebhookRule(body: Omit<WebhookRule, "id" | "last_digest_at" | "created_at">) {
  const res = await fetch("/api/webhook-notifications/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create notification rule");
  return res.json() as Promise<WebhookRule>;
}

export async function patchWebhookRule(id: number, body: Partial<WebhookRule>) {
  const res = await fetch(`/api/webhook-notifications/rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update notification rule");
  return res.json() as Promise<WebhookRule>;
}

export async function deleteWebhookRule(id: number) {
  const res = await fetch(`/api/webhook-notifications/rules/${id}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("Failed to delete notification rule");
  return res.json();
}

export async function fetchWebhookDeliveries(): Promise<WebhookDelivery[]> {
  const res = await fetch("/api/webhook-notifications/deliveries", {
    cache: "no-store",
    credentials: "same-origin",
  });
  return res.ok ? res.json() : [];
}

export function defaultMatchJson(eventType: string): string {
  switch (eventType) {
    case "skill_queue_low":
      return JSON.stringify({ max_queue_size: 5 });
    case "wallet_below":
    case "wallet_above":
      return JSON.stringify({ wallet_threshold_isk: "100000000" });
    case "mail_subject_match":
      return JSON.stringify({ patterns: ["important", "contract"], regex: false });
    case "pi_extraction_complete":
    case "pi_planet_idle":
      return JSON.stringify({ planet_ids: [] });
    case "pi_extractor_expiring":
      return JSON.stringify({ planet_ids: [], hours_before: 4 });
    case "pi_storage_attention":
      return JSON.stringify({ planet_ids: [], storage_pct: 85 });
    case "contract_accepted":
    case "contract_completed":
    case "contract_expired":
    case "contract_issued":
      return JSON.stringify({ contract_types: [], title_contains: "" });
    default:
      return "{}";
  }
}
