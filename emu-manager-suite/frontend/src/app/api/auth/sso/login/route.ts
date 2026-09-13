import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY, publicAppUrl } from "@/lib/bff";

export async function GET(req: NextRequest) {
  try {
    const res = await fetch(`${EMUMS_API_URL}/auth/sso/login-url`, {
      headers: { "X-EMUMS-Key": EMUMS_API_KEY },
      cache: "no-store",
    });
    const data = (await res.json()) as { configured?: boolean; url?: string };

    if (!res.ok || !data.url) {
      return NextResponse.redirect(publicAppUrl(req, "/?sso_error=login_unavailable"));
    }

    return NextResponse.redirect(data.url);
  } catch (err) {
    console.error("EMUMS SSO login redirect failed:", err);
    return NextResponse.redirect(publicAppUrl(req, "/?sso_error=server_error"));
  }
}
