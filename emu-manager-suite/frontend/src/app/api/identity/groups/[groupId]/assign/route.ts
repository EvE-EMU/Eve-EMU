import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ groupId: string }> }
) {
  const { groupId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/identity/groups/${groupId}/assign`, req, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}
