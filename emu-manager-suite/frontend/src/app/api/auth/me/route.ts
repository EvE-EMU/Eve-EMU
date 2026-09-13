import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const session = req.cookies.get("emums_session")?.value;
  const res = await fetch(`${EMUMS_API_URL}/auth/me`, {
    headers: {
      "X-EMUMS-Key": EMUMS_API_KEY,
      ...(session ? { "X-EMUMS-Session": session } : {}),
    },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
