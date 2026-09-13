import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: Request) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/audit/sync-all/enqueue", req, { method: "POST" })
  );
}
