import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_KEY, EMUMS_API_URL } from "@/lib/bff";
import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const session = req.cookies.get("emums_session")?.value;
  const meRes = await fetch(`${EMUMS_API_URL}/auth/me`, {
    headers: {
      "X-EMUMS-Key": EMUMS_API_KEY,
      ...(session ? { "X-EMUMS-Session": session } : {}),
    },
    cache: "no-store",
  });
  const me = meRes.ok ? await meRes.json() : { authenticated: false };
  if (!me.authenticated) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }
  return emumsJsonResponse(await emumsBackendFetch("/dashboard"));
}
