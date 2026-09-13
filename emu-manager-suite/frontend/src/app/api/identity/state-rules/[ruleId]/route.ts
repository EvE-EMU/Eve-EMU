import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ ruleId: string }> }
) {
  const { ruleId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/identity/state-rules/${ruleId}`, req, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}
