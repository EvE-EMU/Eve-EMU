import type { OrgSettings } from "@/lib/api";

export type SettingsUpdate = Partial<
  Pick<
    OrgSettings,
    | "org_name"
    | "tax_corp_name"
    | "corporation_id"
    | "observer_corporation_id"
    | "mail_enabled"
    | "mail_sender_character"
    | "propaganda_tagline"
  >
>;

export async function updateSettings(payload: SettingsUpdate): Promise<OrgSettings> {
  const res = await fetch("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save settings");
  return res.json() as Promise<OrgSettings>;
}
