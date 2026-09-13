import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch, publicAppUrl } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const res = await emumsAuthedBackendFetch("/auth/sso/link-url", req);
    if (!res.ok) {
      return NextResponse.redirect(publicAppUrl(req, "/?sso_error=link_unavailable"));
    }
    const data = (await res.json()) as { url?: string };
    if (!data.url) {
      return NextResponse.redirect(publicAppUrl(req, "/?sso_error=link_unavailable"));
    }
    return NextResponse.redirect(data.url);
  } catch (err) {
    console.error("EMUMS SSO link redirect failed:", err);
    return NextResponse.redirect(publicAppUrl(req, "/?sso_error=server_error"));
  }
}
