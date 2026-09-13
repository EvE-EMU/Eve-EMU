import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/settings", req);
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function PATCH(req: NextRequest) {
  const payload = await req.text();
  const res = await emumsAuthedBackendFetch("/settings", req, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: payload,
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
