import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function PATCH(req: Request) {
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch("/admin/services/lock", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
