/** Sync desktop URL without a full Next.js navigation. */
export function syncDesktopUrl(options?: {
  tool?: string | null;
  section?: string | null;
  marketType?: { typeId: number; typeName: string } | null;
}) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (url.pathname !== "/") url.pathname = "/";
  if (options?.tool) url.searchParams.set("tool", options.tool);
  else if (options && "tool" in options) url.searchParams.delete("tool");
  if (options?.marketType) {
    url.searchParams.set("type_id", String(options.marketType.typeId));
    url.searchParams.set("type_name", options.marketType.typeName);
  } else if (options && "marketType" in options) {
    url.searchParams.delete("type_id");
    url.searchParams.delete("type_name");
  }
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export function openToolInDesktop(
  slug: string,
  windowId: string,
  openWindow: (id: string) => void,
  focusWindow: (id: string) => void
) {
  openWindow(windowId);
  focusWindow(windowId);
  syncDesktopUrl({ tool: slug });
}
