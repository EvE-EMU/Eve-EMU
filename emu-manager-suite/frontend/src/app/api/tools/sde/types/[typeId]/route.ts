import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ typeId: string }> }
) {
  const { typeId } = await params;
  const includeSkillCheck = req.nextUrl.searchParams.get("include_skill_check") ?? "true";
  const url = `${EMUMS_API_URL}/tools/intelligence/sde/types/${typeId}/detail?include_skill_check=${includeSkillCheck}`;
  const res = await fetch(url, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    next: { revalidate: 3600 },
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
