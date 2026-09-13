import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const res = await emumsAuthedBackendFetch(
    `/tools/suite/ship-compare${qs ? `?${qs}` : ""}`,
    req
  );
  return emumsJsonResponse(res);
}
