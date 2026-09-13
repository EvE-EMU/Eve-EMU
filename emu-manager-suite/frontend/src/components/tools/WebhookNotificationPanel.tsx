"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useAuth } from "@/components/AuthProvider";
import { EveTable, SectionHead } from "@/components/ui";
import {
  createWebhookRule,
  defaultMatchJson,
  deleteWebhookRule,
  fetchWebhookCatalog,
  fetchWebhookDeliveries,
  fetchWebhookRules,
  patchWebhookRule,
  type WebhookDelivery,
  type WebhookEventDef,
  type WebhookRule,
} from "@/lib/webhookNotifications";

const MATCH_HINTS: Record<string, string> = {
  wallet_threshold_isk: "ISK amount as string, e.g. 100000000",
  max_queue_size: "Fire when queue drops below this count (default 5)",
  patterns: 'JSON array, e.g. ["recruit","contract"]',
  contract_types: 'Optional filter: ["item_exchange","auction"]',
  title_contains: "Substring match on contract title",
  skill_type_ids: "Optional list of skill type IDs to watch",
  scope_keys: 'Optional: ["wallet","mail","token"]',
  planet_ids: "Optional list of planet IDs to watch (empty = all)",
  hours_before: "Alert when extractor head expires within N hours (default 4)",
  storage_pct: "Alert when storage fill % crosses threshold (default 85)",
};

export function WebhookNotificationPanel() {
  const { session } = useAuth();
  const [catalog, setCatalog] = useState<{ events: WebhookEventDef[]; delivery_modes: { id: string; label: string }[] } | null>(null);
  const [rules, setRules] = useState<WebhookRule[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [tab, setTab] = useState<"rules" | "deliveries">("rules");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    event_type: "skill_training_complete",
    delivery_mode: "instant",
    webhook_url: "",
    notify_in_app: true,
    all_characters: true,
    target_character_id: "",
    match_json: defaultMatchJson("skill_training_complete"),
  });

  const load = useCallback(async () => {
    try {
      const [cat, rows, log] = await Promise.all([
        fetchWebhookCatalog(),
        fetchWebhookRules(),
        fetchWebhookDeliveries(),
      ]);
      setCatalog(cat);
      setRules(rows);
      setDeliveries(log);
      setError(null);
    } catch {
      setError("Unable to load webhook notification settings.");
    }
  }, []);

  useEffect(() => {
    if (session.authenticated) void load();
  }, [session.authenticated, load]);

  const selectedEvent = useMemo(
    () => catalog?.events.find((e) => e.event_type === form.event_type),
    [catalog?.events, form.event_type]
  );

  if (!session.authenticated) {
    return <p className="text-[11px] text-[var(--text-muted)] p-3">Log in to configure webhook notifications.</p>;
  }

  return (
    <div className="text-[11px] space-y-3 p-1">
      <div>
        <h2 className="text-[13px] font-medium">Webhook notifications</h2>
        <p className="text-[10px] text-[var(--text-muted)] mt-1">
          Create alerts for skill training, contracts, wallet thresholds, mail subjects, and more. Deliver instantly or
          on a digest schedule to any Discord/webhook URL. Rules evaluate on each character audit sync across your
          linked alts.
        </p>
      </div>

      {error ? <p className="text-[var(--danger)]">{error}</p> : null}

      <div className="flex gap-1">
        {(["rules", "deliveries"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={clsx("eve-btn-sm", tab === t && "eve-btn-primary")}
            onClick={() => setTab(t)}
          >
            {t === "rules" ? `Rules (${rules.length})` : `Delivery log (${deliveries.length})`}
          </button>
        ))}
        <button type="button" className="eve-btn-sm ml-auto" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {tab === "rules" ? (
        <>
          <form
            className="border border-[var(--border)] p-3 space-y-2 grid grid-cols-2 gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void createWebhookRule({
                name: form.name,
                description: form.description,
                enabled: true,
                event_type: form.event_type,
                match_json: form.match_json,
                webhook_url: form.webhook_url,
                notify_in_app: form.notify_in_app,
                delivery_mode: form.delivery_mode,
                all_characters: form.all_characters,
                target_character_id: form.all_characters
                  ? null
                  : Number(form.target_character_id) || null,
              })
                .then((row) => {
                  setRules((prev) => [...prev, row]);
                  setForm((f) => ({ ...f, name: "", description: "" }));
                })
                .catch(() => setError("Failed to create rule."));
            }}
          >
            <SectionHead>Create rule</SectionHead>
            <input
              className="eve-input col-span-2"
              placeholder="Rule name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
            <select
              className="eve-select"
              value={form.event_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  event_type: e.target.value,
                  match_json: defaultMatchJson(e.target.value),
                }))
              }
            >
              {(catalog?.events ?? []).map((ev) => (
                <option key={ev.event_type} value={ev.event_type}>
                  {ev.label}
                </option>
              ))}
            </select>
            <select
              className="eve-select"
              value={form.delivery_mode}
              onChange={(e) => setForm((f) => ({ ...f, delivery_mode: e.target.value }))}
            >
              {(catalog?.delivery_modes ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            {selectedEvent ? (
              <p className="col-span-2 text-[10px] text-[var(--text-muted)]">{selectedEvent.description}</p>
            ) : null}
            <input
              className="eve-input col-span-2"
              placeholder="Webhook URL (Discord-compatible)"
              value={form.webhook_url}
              onChange={(e) => setForm((f) => ({ ...f, webhook_url: e.target.value }))}
            />
            <label className="flex items-center gap-2 col-span-2">
              <input
                type="checkbox"
                checked={form.all_characters}
                onChange={(e) => setForm((f) => ({ ...f, all_characters: e.target.checked }))}
              />
              Apply to all linked characters
            </label>
            {!form.all_characters ? (
              <select
                className="eve-select col-span-2"
                value={form.target_character_id}
                onChange={(e) => setForm((f) => ({ ...f, target_character_id: e.target.value }))}
                required
              >
                <option value="">Select character…</option>
                {(session.alts ?? []).map((a) => (
                  <option key={a.character_id} value={a.character_id}>
                    {a.character_name}
                  </option>
                ))}
              </select>
            ) : null}
            <div className="col-span-2">
              <label className="text-[10px] text-[var(--text-muted)] block mb-1">
                Logic / filters (match_json)
                {selectedEvent?.match_fields.length
                  ? ` — fields: ${selectedEvent.match_fields.join(", ")}`
                  : ""}
              </label>
              <textarea
                className="eve-input w-full font-mono text-[10px] min-h-[64px]"
                value={form.match_json}
                onChange={(e) => setForm((f) => ({ ...f, match_json: e.target.value }))}
              />
              {selectedEvent?.match_fields.map((field) => (
                <p key={field} className="text-[9px] text-[var(--text-dim)]">
                  {field}: {MATCH_HINTS[field] ?? "See catalog"}
                </p>
              ))}
            </div>
            <label className="flex items-center gap-2 col-span-2">
              <input
                type="checkbox"
                checked={form.notify_in_app}
                onChange={(e) => setForm((f) => ({ ...f, notify_in_app: e.target.checked }))}
              />
              Also show in EMUMS notification bell
            </label>
            <button type="submit" className="eve-btn-sm eve-btn-primary col-span-2">
              Add notification rule
            </button>
          </form>

          <EveTable
            headers={[
              { label: "Rule" },
              { label: "Event" },
              { label: "Delivery" },
              { label: "Scope" },
              { label: "On" },
              { label: "" },
            ]}
          >
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <div>{rule.name}</div>
                  <div className="text-[9px] text-[var(--text-dim)] truncate max-w-[140px]" title={rule.webhook_url}>
                    {rule.webhook_url ? "Webhook set" : "No webhook"}
                  </div>
                </td>
                <td className="text-[10px]">{rule.event_type.replace(/_/g, " ")}</td>
                <td>{rule.delivery_mode}</td>
                <td className="text-[10px]">{rule.all_characters ? "All alts" : `Char ${rule.target_character_id}`}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={rule.enabled}
                    onChange={(e) =>
                      void patchWebhookRule(rule.id, { enabled: e.target.checked }).then((updated) =>
                        setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)))
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="eve-btn-sm text-[var(--danger)]"
                    onClick={() =>
                      void deleteWebhookRule(rule.id).then(() =>
                        setRules((prev) => prev.filter((r) => r.id !== rule.id))
                      )
                    }
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </EveTable>
          {!rules.length ? (
            <p className="text-[10px] text-[var(--text-muted)]">No rules yet — create one above.</p>
          ) : null}
        </>
      ) : (
        <EveTable headers={[{ label: "When" }, { label: "Mode" }, { label: "Events" }, { label: "Status" }, { label: "Detail" }]}>
          {deliveries.map((d) => (
            <tr key={d.id}>
              <td className="text-[10px] text-[var(--text-muted)]">
                {d.created_at ? new Date(d.created_at).toLocaleString() : "—"}
              </td>
              <td>{d.delivery_mode}</td>
              <td className="font-mono">{d.event_count}</td>
              <td className={clsx(d.webhook_status === "ok" && "text-[var(--ok)]", d.webhook_status === "error" && "text-[var(--danger)]")}>
                {d.webhook_status}
              </td>
              <td className="text-[10px] truncate max-w-[200px]" title={d.detail}>
                {d.detail}
              </td>
            </tr>
          ))}
        </EveTable>
      )}
    </div>
  );
}
