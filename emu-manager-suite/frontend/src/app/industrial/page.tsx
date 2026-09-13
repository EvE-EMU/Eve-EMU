import { redirect } from "next/navigation";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

/**
 * EMUMS legacy /industrial entry → core-web industrial command deck.
 * Preserves query params; maps old desktop window ids onto industrial tabs when present.
 */
export default async function LegacyIndustrialRedirect({ searchParams }: Props) {
  const params = await searchParams;
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string") q.set(key, value);
    else if (Array.isArray(value) && value[0]) q.set(key, value[0]);
  }
  const tool = (q.get("tool") || q.get("window") || "").toLowerCase();
  const tabMap: Record<string, string> = {
    "ip-planner": "forge",
    "ip-blueprints": "forge",
    "ip-projects": "projects",
    "ip-storefront": "market",
    planner: "forge",
    projects: "projects",
    storefront: "market",
  };
  if (!q.has("tab") && tool && tabMap[tool]) {
    q.set("tab", tabMap[tool]);
  }
  if (!q.has("tab")) q.set("tab", "forge");
  const qs = q.toString();
  redirect(`https://eve-emu.com/industrial${qs ? `?${qs}` : ""}`);
}
