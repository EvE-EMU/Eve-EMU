import { loadDesktopData } from "@/lib/loadDesktopData";
import { UnifiedDesktop } from "@/components/UnifiedDesktop";

export const dynamic = "force-dynamic";

export default async function CommandDashboard() {
  const data = await loadDesktopData();
  return <UnifiedDesktop data={data} />;
}
