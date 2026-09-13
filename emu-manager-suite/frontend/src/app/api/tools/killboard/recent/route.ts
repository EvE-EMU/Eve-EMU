import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit") ?? "50";
  const res = await emumsBackendFetch(
    `/tools/intelligence/killboard/recent?scope=alliance&limit=${encodeURIComponent(limit)}`
  );
  return emumsTextJsonResponse(res);
}
