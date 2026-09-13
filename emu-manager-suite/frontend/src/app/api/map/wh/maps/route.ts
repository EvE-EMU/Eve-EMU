import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/map/wh/maps"));
}

export async function POST(req: Request) {
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch("/map/wh/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
