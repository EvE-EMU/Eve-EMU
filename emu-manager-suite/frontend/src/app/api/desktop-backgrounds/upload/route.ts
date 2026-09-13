import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export const runtime = "nodejs";
export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const res = await fetch(`${EMUMS_API_URL}/ui/desktop-backgrounds/upload`, {
      method: "POST",
      headers: { "X-EMUMS-Key": EMUMS_API_KEY },
      body: form,
      cache: "no-store",
    });

    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Upload service unavailable. Try again or use a video URL." },
      { status: 502 }
    );
  }
}
