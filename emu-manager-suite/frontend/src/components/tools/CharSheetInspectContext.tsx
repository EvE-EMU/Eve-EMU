"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AssetTreeNode } from "@/components/tools/CharacterSheetAssets";

type CharSheetInspectContextValue = {
  openItemInfo: (typeId: number, typeName?: string) => void;
  openShipFitting: (ship: AssetTreeNode, locationName?: string) => void;
  openSystemDetail: (systemId: number, systemName?: string) => void;
  openWikiArticle: (title: string, displayName?: string) => void;
  sdeTypeId: number | null;
  sdeTypeName: string;
  shipNode: AssetTreeNode | null;
  shipLocationName: string;
  systemId: number | null;
  systemName: string;
  wikiTitle: string | null;
  wikiDisplayName: string;
};

const CharSheetInspectContext = createContext<CharSheetInspectContextValue | null>(null);

export function CharSheetInspectProvider({
  children,
  onOpenItemWindow,
  onOpenShipWindow,
  onOpenSystemWindow,
  onOpenWikiWindow,
}: {
  children: ReactNode;
  onOpenItemWindow: (typeId: number, typeName: string) => void;
  onOpenShipWindow: (ship: AssetTreeNode, locationName: string) => void;
  onOpenSystemWindow: (systemId: number, systemName: string) => void;
  onOpenWikiWindow: (title: string, displayName: string) => void;
}) {
  const [sdeTypeId, setSdeTypeId] = useState<number | null>(null);
  const [sdeTypeName, setSdeTypeName] = useState("Item details");
  const [shipNode, setShipNode] = useState<AssetTreeNode | null>(null);
  const [shipLocationName, setShipLocationName] = useState("");
  const [systemId, setSystemId] = useState<number | null>(null);
  const [systemName, setSystemName] = useState("System details");
  const [wikiTitle, setWikiTitle] = useState<string | null>(null);
  const [wikiDisplayName, setWikiDisplayName] = useState("Wiki article");

  const openItemInfo = useCallback(
    (typeId: number, typeName?: string) => {
      setSdeTypeId(typeId);
      setSdeTypeName(typeName || "Item details");
      onOpenItemWindow(typeId, typeName || "Item details");
    },
    [onOpenItemWindow]
  );

  const openShipFitting = useCallback(
    (ship: AssetTreeNode, locationName?: string) => {
      setShipNode(ship);
      setShipLocationName(locationName || "");
      onOpenShipWindow(ship, locationName || "");
    },
    [onOpenShipWindow]
  );

  const openSystemDetail = useCallback(
    (sid: number, name?: string) => {
      setSystemId(sid);
      setSystemName(name || "System details");
      onOpenSystemWindow(sid, name || "System details");
    },
    [onOpenSystemWindow]
  );

  const openWikiArticle = useCallback(
    (title: string, displayName?: string) => {
      setWikiTitle(title);
      setWikiDisplayName(displayName || title.split("/").pop() || "Wiki article");
      onOpenWikiWindow(title, displayName || title.split("/").pop() || "Wiki article");
    },
    [onOpenWikiWindow]
  );

  const value = useMemo(
    () => ({
      openItemInfo,
      openShipFitting,
      openSystemDetail,
      openWikiArticle,
      sdeTypeId,
      sdeTypeName,
      shipNode,
      shipLocationName,
      systemId,
      systemName,
      wikiTitle,
      wikiDisplayName,
    }),
    [
      openItemInfo,
      openShipFitting,
      openSystemDetail,
      openWikiArticle,
      sdeTypeId,
      sdeTypeName,
      shipNode,
      shipLocationName,
      systemId,
      systemName,
      wikiTitle,
      wikiDisplayName,
    ]
  );

  return <CharSheetInspectContext.Provider value={value}>{children}</CharSheetInspectContext.Provider>;
}

export function useCharSheetInspect() {
  return useContext(CharSheetInspectContext);
}
