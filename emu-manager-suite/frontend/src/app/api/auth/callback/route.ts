import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY, publicAppUrl } from "@/lib/bff";
import { mapExchangeDetail } from "@/lib/ssoMessages";

export async function GET(req: NextRequest) {
  try {
    const code = req.nextUrl.searchParams.get("code");
    const state = req.nextUrl.searchParams.get("state") ?? "";
    const error = req.nextUrl.searchParams.get("error");

    if (error) {
      return NextResponse.redirect(publicAppUrl(req, `/?sso_error=${encodeURIComponent(error)}`));
    }
    if (!code) {
      return NextResponse.redirect(publicAppUrl(req, "/?sso_error=missing_code"));
    }

    const res = await fetch(`${EMUMS_API_URL}/auth/sso/exchange`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-EMUMS-Key": EMUMS_API_KEY,
      },
      body: JSON.stringify({ code, state }),
      cache: "no-store",
    });

    if (!res.ok) {
      const detail = await res.text();
      console.error("EMUMS SSO exchange failed:", res.status, detail);
      let codeKey = "exchange_failed";
      try {
        const parsed = JSON.parse(detail) as { detail?: string };
        if (parsed.detail) codeKey = mapExchangeDetail(parsed.detail);
      } catch {
        if (res.status >= 500) codeKey = "server_error";
      }
      return NextResponse.redirect(publicAppUrl(req, `/?sso_error=${encodeURIComponent(codeKey)}`));
    }

    const data = (await res.json()) as { session_token?: string; linked?: boolean };

    if (data.linked) {
      return NextResponse.redirect(publicAppUrl(req, "/?alt_linked=1"));
    }

    if (!data.session_token) {
      return NextResponse.redirect(publicAppUrl(req, "/?sso_error=no_session"));
    }

    const response = NextResponse.redirect(publicAppUrl(req, "/"));
    response.cookies.set("emums_session", data.session_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  } catch (err) {
    console.error("EMUMS SSO callback error:", err);
    return NextResponse.redirect(publicAppUrl(req, "/?sso_error=server_error"));
  }
}
