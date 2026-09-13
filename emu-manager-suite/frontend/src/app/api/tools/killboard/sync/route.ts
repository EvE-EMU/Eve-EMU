import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  const res = await emumsBackendFetch("/tools/intelligence/killboard/sync", { method: "POST" });
  return emumsTextJsonResponse(res);
}
