import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: Request) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/audit/me/sync", req, { method: "POST" })
  );
}
