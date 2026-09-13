import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: Request) {
  return emumsJsonResponse(await emumsAuthedBackendFetch("/audit/me", req));
}
