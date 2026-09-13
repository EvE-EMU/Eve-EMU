import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const params = new URL(req.url).searchParams.toString();
  const path = params ? `/identity/admin/users/search?${params}` : "/identity/admin/users/search";
  return emumsJsonResponse(await emumsAuthedBackendFetch(path, req));
}
