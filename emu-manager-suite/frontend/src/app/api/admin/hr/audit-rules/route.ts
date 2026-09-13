import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/admin/hr/audit-rules"));
}

export async function POST(req: Request) {
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch("/admin/hr/audit-rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
