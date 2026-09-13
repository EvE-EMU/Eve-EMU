import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await emumsAuthedBackendFetch("/auth/switch", req, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  if (!res.ok) {
    return emumsJsonResponse(res);
  }
  const data = (await res.json()) as { session_token?: string };
  const response = NextResponse.json(data);
  if (data.session_token) {
    response.cookies.set("emums_session", data.session_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return response;
}
