"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useWindowManager } from "@/components/WindowManager";
import { openToolInDesktop, syncDesktopUrl } from "@/lib/openTool";

export type MarketBrowserFocus = {
  typeId: number;
  typeName: string;
  nonce: number;
  autoLoad: boolean;
};

type MarketBrowserContextValue = {
  focus: MarketBrowserFocus | null;
  openMarketBrowser: (typeId: number, typeName: string, options?: { autoLoad?: boolean }) => void;
  warmMarketHistory: (typeId: number) => void;
};

const MarketBrowserContext = createContext<MarketBrowserContextValue | null>(null);

export function MarketBrowserProvider({ children }: { children: ReactNode }) {
  const { openWindow, focusWindow } = useWindowManager();
  const [focus, setFocus] = useState<MarketBrowserFocus | null>(null);

  const warmMarketHistory = useCallback((typeId: number) => {
    if (!Number.isFinite(typeId) || typeId <= 0) return;
    void fetch(`/api/tools/market-browser/warm?type_id=${typeId}`, {
      method: "POST",
      credentials: "same-origin",
    }).catch(() => undefined);
  }, []);

  const openMarketBrowser = useCallback(
    (typeId: number, typeName: string, options?: { autoLoad?: boolean }) => {
      if (!Number.isFinite(typeId) || typeId <= 0) return;
      const label = typeName.trim() || `Type ${typeId}`;
      setFocus({
        typeId,
        typeName: label,
        nonce: Date.now(),
        autoLoad: options?.autoLoad !== false,
      });
      openToolInDesktop("market-browser", "market-browser", openWindow, focusWindow);
      syncDesktopUrl({
        tool: "market-browser",
        marketType: { typeId, typeName: label },
      });
      warmMarketHistory(typeId);
    },
    [focusWindow, openWindow, warmMarketHistory]
  );

  const value = useMemo(
    () => ({ focus, openMarketBrowser, warmMarketHistory }),
    [focus, openMarketBrowser, warmMarketHistory]
  );

  return <MarketBrowserContext.Provider value={value}>{children}</MarketBrowserContext.Provider>;
}

export function useMarketBrowser() {
  return useContext(MarketBrowserContext);
}
