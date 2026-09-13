import { redirect } from "next/navigation";

/** Preserve query params when moving legacy routes onto the unified desktop at `/`. */
export function redirectToDesktop(
  searchParams: Record<string, string | string[] | undefined>,
  defaultTool?: string
): never {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === "string") q.set(key, value);
    else if (Array.isArray(value) && value[0]) q.set(key, value[0]);
  }
  if (defaultTool && !q.has("tool")) q.set("tool", defaultTool);
  const query = q.toString();
  redirect(query ? `/?${query}` : "/");
}
