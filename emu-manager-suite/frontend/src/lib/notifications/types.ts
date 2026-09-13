/** Extensible notification type registry — addons register plugin + type metadata. */

export type NotificationRecord = {
  id: number;
  plugin: string;
  type: string;
  title: string;
  body: string;
  payload_json: string;
  recipient_character_id?: number | null;
  read: boolean;
  created_at: string;
};

export type NotificationTypeMeta = {
  plugin: string;
  type: string;
  label: string;
  icon?: "moon" | "tax" | "rental" | "extraction" | "info" | "alert";
};

const REGISTRY = new Map<string, NotificationTypeMeta>();

export function notificationKey(plugin: string, type: string) {
  return `${plugin}:${type}`;
}

/** Register notification types from an addon/plugin at module load. */
export function registerNotificationTypes(types: NotificationTypeMeta[]) {
  for (const t of types) {
    REGISTRY.set(notificationKey(t.plugin, t.type), t);
  }
}

export function getNotificationMeta(plugin: string, type: string): NotificationTypeMeta {
  return (
    REGISTRY.get(notificationKey(plugin, type)) ?? {
      plugin,
      type,
      label: type.replace(/_/g, " "),
      icon: "info",
    }
  );
}

registerNotificationTypes([
  { plugin: "moons", type: "tax_bill", label: "Tax bill", icon: "tax" },
  { plugin: "moons", type: "extraction_ready", label: "Extraction", icon: "extraction" },
  { plugin: "storefront", type: "order", label: "Storefront order", icon: "info" },
  { plugin: "system", type: "info", label: "System", icon: "info" },
  { plugin: "system", type: "alert", label: "Alert", icon: "alert" },
]);
