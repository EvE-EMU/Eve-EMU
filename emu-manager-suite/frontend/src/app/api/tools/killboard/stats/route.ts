import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const res = await emumsBackendFetch("/tools/intelligence/killboard/stats?scope=alliance");
  return emumsTextJsonResponse(res);
}
