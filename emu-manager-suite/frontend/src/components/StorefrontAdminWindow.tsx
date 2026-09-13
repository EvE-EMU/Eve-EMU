"use client";

import { useCallback, useEffect, useState } from "react";
import { EveTable, EveWindow, SectionHead } from "@/components/ui";
import type { StorefrontCatalog, StorefrontPickupLocation } from "@/lib/api";

type StorefrontConfig = {
  enabled: boolean;
  corp_name: string;
  corp_id: number;
  inventory_character_ids: string;
  corp_hangar_flag: string;
  structure_id: number;
  structure_name_contains: string;
  system_name_contains: string;
  price_hub: string;
  discord_webhook_url: string;
  staff_notify_character_id: number;
  contract_expiration_hours: number;
};

type OverrideRow = {
  id: number;
  type_id: number;
  type_name: string;
  price_override_isk: number | null;
  fake_qty_add: number;
  hidden: boolean;
  note: string;
};

type KitRow = {
  id: number;
  name: string;
  description: string;
  price_isk: number | null;
  active: boolean;
  items: { type_id: number; type_name: string; quantity: number }[];
};

type OrderRow = {
  id: number;
  order_code: string;
  buyer_character_name: string;
  total_isk: number;
  status: string;
  mail_sent_buyer?: boolean;
  mail_sent_corp?: boolean;
  discord_sent?: boolean;
  mail_error?: string | null;
  created_at: string | null;
};

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = (await res.json()) as T & { detail?: string; message?: string };
  if (!res.ok) {
    throw new Error(String(data.detail || data.message || `Request failed (${res.status})`));
  }
  return data;
}

export function StorefrontAdminWindow() {
  const [tab, setTab] = useState<"settings" | "locations" | "inventory" | "kits" | "orders">("settings");
  const [config, setConfig] = useState<StorefrontConfig | null>(null);
  const [catalog, setCatalog] = useState<StorefrontCatalog | null>(null);
  const [locations, setLocations] = useState<StorefrontPickupLocation[]>([]);
  const [overrides, setOverrides] = useState<OverrideRow[]>([]);
  const [kits, setKits] = useState<KitRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [overrideForm, setOverrideForm] = useState({
    type_id: "",
    type_name: "",
    price_override_isk: "",
    fake_qty_add: "0",
    hidden: false,
    note: "",
  });
  const [kitForm, setKitForm] = useState({
    name: "",
    description: "",
    price_isk: "",
    items_json: "34 1000\n35 500",
  });
  const [locForm, setLocForm] = useState({
    label: "",
    structure_name: "",
    structure_id: "",
    system_name: "",
    location_hint: "",
    is_default: false,
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [cfgRes, catRes, locRes, ovRes, kitRes, ordRes] = await Promise.all([
        fetch("/api/admin/storefront/config"),
        fetch("/api/admin/storefront/catalog"),
        fetch("/api/admin/storefront/locations"),
        fetch("/api/admin/storefront/overrides"),
        fetch("/api/admin/storefront/kits"),
        fetch("/api/admin/storefront/orders"),
      ]);
      if (cfgRes.ok) setConfig(await cfgRes.json());
      if (catRes.ok) setCatalog(await catRes.json());
      if (locRes.ok) setLocations(await locRes.json());
      if (ovRes.ok) setOverrides(await ovRes.json());
      if (kitRes.ok) setKits(await kitRes.json());
      if (ordRes.ok) setOrders(await ordRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveConfig = async () => {
    if (!config) return;
    setMessage("");
    setError("");
    try {
      await apiJson("/api/admin/storefront/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      setMessage("Settings saved.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const addOverride = async () => {
    const tid = parseInt(overrideForm.type_id, 10);
    if (!tid) return;
    setError("");
    try {
      await apiJson("/api/admin/storefront/overrides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type_id: tid,
          type_name: overrideForm.type_name,
          price_override_isk: overrideForm.price_override_isk ? parseFloat(overrideForm.price_override_isk) : null,
          fake_qty_add: parseInt(overrideForm.fake_qty_add, 10) || 0,
          hidden: overrideForm.hidden,
          note: overrideForm.note,
        }),
      });
      setOverrideForm({ type_id: "", type_name: "", price_override_isk: "", fake_qty_add: "0", hidden: false, note: "" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Override failed");
    }
  };

  const deleteOverride = async (id: number) => {
    try {
      await apiJson(`/api/admin/storefront/overrides/${id}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const parseKitItems = (text: string) =>
    text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [a, b] = line.split(/\s+/);
        return { type_id: parseInt(a, 10), type_name: "", quantity: parseInt(b, 10) || 1 };
      })
      .filter((r) => r.type_id > 0);

  const addKit = async () => {
    if (!kitForm.name.trim()) return;
    setError("");
    try {
      await apiJson("/api/admin/storefront/kits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: kitForm.name.trim(),
          description: kitForm.description,
          price_isk: kitForm.price_isk ? parseFloat(kitForm.price_isk) : null,
          items: parseKitItems(kitForm.items_json),
        }),
      });
      setKitForm({ name: "", description: "", price_isk: "", items_json: kitForm.items_json });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kit create failed");
    }
  };

  const addLocation = async () => {
    if (!locForm.label.trim()) return;
    setError("");
    try {
      await apiJson("/api/admin/storefront/locations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: locForm.label.trim(),
          structure_name: locForm.structure_name,
          structure_id: parseInt(locForm.structure_id, 10) || 0,
          system_name: locForm.system_name,
          location_hint: locForm.location_hint,
          is_default: locForm.is_default,
          active: true,
        }),
      });
      setLocForm({ label: "", structure_name: "", structure_id: "", system_name: "", location_hint: "", is_default: false });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Location create failed");
    }
  };

  const patchOrderStatus = async (id: number, status: string) => {
    try {
      await apiJson(`/api/admin/storefront/orders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status update failed");
    }
  };

  return (
    <EveWindow
      id="admin-storefront"
      title="Storefront manager"
      defaultX={480}
      defaultY={48}
      defaultWidth={620}
      defaultHeight={560}
    >
      <p className="text-[10px] text-[var(--text-muted)] mb-2">
        Corp {config?.corp_id ?? 98829530} hangar 1 @ all structures · Janice Jita split · WTB orders.
      </p>
      {catalog?.inventory_source ? (
        <p className="text-[10px] text-[var(--text-muted)] mb-2">
          Synced characters: {catalog.inventory_source.inventory_character_ids?.length ?? catalog.inventory_source.sync_character_count ?? 0}
          {" · "}
          Hangar types: {catalog.inventory_source.sync_hangar_type_count ?? 0}
          {" · "}
          Corp assets scope: {catalog.inventory_source.corp_assets_scope_count ?? 0}/{catalog.inventory_source.sync_character_count ?? 0}
          {" · "}
          Catalog items: {catalog.items.length}
          {(catalog.inventory_source.sync_character_count ?? 0) > 0 &&
          (catalog.inventory_source.sync_hangar_type_count ?? 0) === 0 ? (
            <>
              {" · "}
              {(catalog.inventory_source.corp_assets_scope_count ?? 0) === 0
                ? "Re-link stock alt via SSO (corporation assets scope), then Audit → Sync."
                : "Audit → Sync stock alt to pull corp hangar 1."}
            </>
          ) : null}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-1 mb-2 text-[10px]">
        {(["settings", "locations", "inventory", "kits", "orders"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`eve-btn-sm ${tab === t ? "eve-btn-primary" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <button type="button" className="eve-btn-sm ml-auto" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </div>
      {error ? <p className="text-[var(--danger)] text-[10px] mb-1">{error}</p> : null}
      {message ? <p className="text-[var(--ok)] text-[10px] mb-1">{message}</p> : null}

      {tab === "settings" && config ? (
        <div className="grid grid-cols-2 gap-1 text-[10px]">
          <label className="col-span-2 flex items-center gap-2">
            <input type="checkbox" checked={config.enabled} onChange={(e) => setConfig({ ...config, enabled: e.target.checked })} />
            Storefront enabled
          </label>
          <label>
            Corporation ID
            <input className="eve-input w-full mt-0.5" value={String(config.corp_id || "")} onChange={(e) => setConfig({ ...config, corp_id: parseInt(e.target.value, 10) || 0 })} />
          </label>
          <label>
            Corp name
            <input className="eve-input w-full mt-0.5" value={config.corp_name} onChange={(e) => setConfig({ ...config, corp_name: e.target.value })} />
          </label>
          <label>
            Price hub (Janice)
            <select className="eve-select w-full mt-0.5" value={config.price_hub} onChange={(e) => setConfig({ ...config, price_hub: e.target.value })}>
              {["jita", "amarr", "rens", "dodixie", "hek"].map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </label>
          <label>
            Contract expiration (hours)
            <input className="eve-input w-full mt-0.5" type="number" min={1} value={config.contract_expiration_hours} onChange={(e) => setConfig({ ...config, contract_expiration_hours: parseInt(e.target.value, 10) || 24 })} />
          </label>
          <label className="col-span-2">
            Stock alt character IDs or names (optional)
            <input className="eve-input w-full mt-0.5" value={config.inventory_character_ids} onChange={(e) => setConfig({ ...config, inventory_character_ids: e.target.value })} placeholder="2124205220 or Delta Shart Force" />
          </label>
          <label>
            Hangar division
            <input className="eve-input w-full mt-0.5" value={config.corp_hangar_flag} onChange={(e) => setConfig({ ...config, corp_hangar_flag: e.target.value })} placeholder="CorpSAG1" />
          </label>
          <label>
            Structure filter (optional)
            <input className="eve-input w-full mt-0.5" value={config.structure_name_contains} onChange={(e) => setConfig({ ...config, structure_name_contains: e.target.value })} />
          </label>
          <label>
            Discord webhook
            <input className="eve-input w-full mt-0.5" value={config.discord_webhook_url} onChange={(e) => setConfig({ ...config, discord_webhook_url: e.target.value })} />
          </label>
          <label>
            Staff notify char ID
            <input className="eve-input w-full mt-0.5" value={String(config.staff_notify_character_id || "")} onChange={(e) => setConfig({ ...config, staff_notify_character_id: parseInt(e.target.value, 10) || 0 })} />
          </label>
          <button type="button" className="eve-btn eve-btn-primary col-span-2 mt-1" onClick={() => void saveConfig()}>
            Save settings
          </button>
        </div>
      ) : null}

      {tab === "locations" ? (
        <>
          <SectionHead>Add pickup location</SectionHead>
          <div className="grid grid-cols-2 gap-1 mb-2 text-[10px]">
            <input className="eve-input" placeholder="Label" value={locForm.label} onChange={(e) => setLocForm({ ...locForm, label: e.target.value })} />
            <input className="eve-input" placeholder="Structure name" value={locForm.structure_name} onChange={(e) => setLocForm({ ...locForm, structure_name: e.target.value })} />
            <input className="eve-input" placeholder="Structure ID" value={locForm.structure_id} onChange={(e) => setLocForm({ ...locForm, structure_id: e.target.value })} />
            <input className="eve-input" placeholder="System" value={locForm.system_name} onChange={(e) => setLocForm({ ...locForm, system_name: e.target.value })} />
            <input className="eve-input col-span-2" placeholder="Location hint" value={locForm.location_hint} onChange={(e) => setLocForm({ ...locForm, location_hint: e.target.value })} />
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={locForm.is_default} onChange={(e) => setLocForm({ ...locForm, is_default: e.target.checked })} />
              Default pickup
            </label>
            <button type="button" className="eve-btn-sm" onClick={() => void addLocation()}>Add location</button>
          </div>
          <EveTable headers={[{ label: "Label" }, { label: "Structure" }, { label: "System" }, { label: "Default" }]}>
            {locations.map((loc) => (
              <tr key={loc.id}>
                <td>{loc.label}</td>
                <td>{loc.structure_name}</td>
                <td>{loc.system_name}</td>
                <td>{loc.is_default ? "Yes" : ""}</td>
              </tr>
            ))}
          </EveTable>
        </>
      ) : null}

      {tab === "inventory" ? (
        <>
          <SectionHead>Overrides / fake stock</SectionHead>
          <div className="grid grid-cols-3 gap-1 mb-2 text-[10px]">
            <input className="eve-input" placeholder="Type ID" value={overrideForm.type_id} onChange={(e) => setOverrideForm({ ...overrideForm, type_id: e.target.value })} />
            <input className="eve-input" placeholder="Name" value={overrideForm.type_name} onChange={(e) => setOverrideForm({ ...overrideForm, type_name: e.target.value })} />
            <input className="eve-input" placeholder="Price override" value={overrideForm.price_override_isk} onChange={(e) => setOverrideForm({ ...overrideForm, price_override_isk: e.target.value })} />
            <input className="eve-input" placeholder="Fake qty" value={overrideForm.fake_qty_add} onChange={(e) => setOverrideForm({ ...overrideForm, fake_qty_add: e.target.value })} />
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={overrideForm.hidden} onChange={(e) => setOverrideForm({ ...overrideForm, hidden: e.target.checked })} />
              Hidden
            </label>
            <button type="button" className="eve-btn-sm" onClick={() => void addOverride()}>Add</button>
          </div>
          <div className="max-h-[200px] overflow-auto mb-2">
            <EveTable headers={[{ label: "Item" }, { label: "Sync", align: "right" }, { label: "Stock", align: "right" }, { label: "Price", align: "right" }]}>
              {(catalog?.items ?? []).filter((i) => i.kind === "item").map((row) => (
                <tr key={row.key}>
                  <td>{row.name}</td>
                  <td className="num">{row.synced_qty}</td>
                  <td className="num">{row.quantity}</td>
                  <td className="num">{row.unit_price_isk != null ? row.unit_price_isk.toLocaleString() : "Contact"}</td>
                </tr>
              ))}
            </EveTable>
          </div>
          {overrides.length ? (
            <EveTable headers={[{ label: "Type" }, { label: "Fake+" }, { label: "Hidden" }, { label: "" }]}>
              {overrides.map((o) => (
                <tr key={o.id}>
                  <td>{o.type_name || o.type_id}</td>
                  <td className="num">{o.fake_qty_add}</td>
                  <td>{o.hidden ? "yes" : ""}</td>
                  <td>
                    <button type="button" className="eve-btn-sm text-[var(--danger)]" onClick={() => void deleteOverride(o.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </EveTable>
          ) : null}
        </>
      ) : null}

      {tab === "kits" ? (
        <>
          <SectionHead>New kit</SectionHead>
          <div className="grid grid-cols-2 gap-1 mb-2 text-[10px]">
            <input className="eve-input" placeholder="Kit name" value={kitForm.name} onChange={(e) => setKitForm({ ...kitForm, name: e.target.value })} />
            <input className="eve-input" placeholder="Price ISK (blank = contact)" value={kitForm.price_isk} onChange={(e) => setKitForm({ ...kitForm, price_isk: e.target.value })} />
            <textarea className="eve-input col-span-2 h-16" placeholder="type_id qty per line" value={kitForm.items_json} onChange={(e) => setKitForm({ ...kitForm, items_json: e.target.value })} />
            <button type="button" className="eve-btn-sm" onClick={() => void addKit()}>Create kit</button>
          </div>
          <EveTable headers={[{ label: "Name" }, { label: "Price" }, { label: "Items" }, { label: "" }]}>
            {kits.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td className="num">{k.price_isk != null ? k.price_isk.toLocaleString() : "Contact"}</td>
                <td>{k.items.map((i) => `${i.type_id}×${i.quantity}`).join(", ")}</td>
                <td>
                  <button type="button" className="eve-btn-sm text-[var(--danger)]" onClick={() => void fetch(`/api/admin/storefront/kits/${k.id}`, { method: "DELETE" }).then(() => refresh())}>Delete</button>
                </td>
              </tr>
            ))}
          </EveTable>
        </>
      ) : null}

      {tab === "orders" ? (
        <EveTable headers={[{ label: "Code" }, { label: "Buyer" }, { label: "Total", align: "right" }, { label: "Status" }, { label: "Notify" }]}>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>{o.order_code}</td>
              <td>{o.buyer_character_name}</td>
              <td className="num">{o.total_isk.toLocaleString()}</td>
              <td>
                <select className="eve-select text-[10px]" value={o.status} onChange={(e) => void patchOrderStatus(o.id, e.target.value)}>
                  {["pending", "accepted", "fulfilled", "cancelled"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </td>
              <td className="text-[9px]">
                {o.mail_sent_buyer ? "mail" : "—"}
                {o.discord_sent ? " · discord" : ""}
                {o.mail_error ? ` · ${o.mail_error}` : ""}
              </td>
            </tr>
          ))}
        </EveTable>
      ) : null}
    </EveWindow>
  );
}
