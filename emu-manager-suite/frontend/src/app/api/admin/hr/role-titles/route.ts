import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/admin/hr/role-titles"));
}

export async function POST(req: Request) {
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch("/admin/hr/role-titles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
