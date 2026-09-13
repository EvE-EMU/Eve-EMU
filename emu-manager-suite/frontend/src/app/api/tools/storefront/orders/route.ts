import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/tools/commerce/storefront/orders", req, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return emumsJsonResponse(res);
}
