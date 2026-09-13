import { NextResponse } from "next/server";
import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: Request) {
  const title = new URL(req.url).searchParams.get("title");
  if (!title) {
    return NextResponse.json({ detail: "title required" }, { status: 400 });
  }
  return emumsJsonResponse(await emumsBackendFetch(`/knowledge/wiki/page?title=${encodeURIComponent(title)}`));
}
