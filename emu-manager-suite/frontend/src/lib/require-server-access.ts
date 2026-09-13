import { canAccessRoute } from "@/lib/permissions";
import { fetchServerSession } from "@/lib/server-session";

/** Returns null when the current visitor may not access this route module. */
export async function requireServerAccess(moduleId: string) {
  const session = await fetchServerSession();
  if (!session || !canAccessRoute(session, moduleId)) return null;
  return session;
}
