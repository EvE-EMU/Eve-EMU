"use client";

import { useCallback, useEffect, useState } from "react";
import { EveWindow } from "@/components/ui";
import { WindowDesktop, useWindowManager } from "@/components/WindowManager";
import { CharacterSheetPanel } from "@/components/tools/CharacterSheetPanel";
import { CharSheetInspectProvider } from "@/components/tools/CharSheetInspectContext";
import { WikiArticlePanel } from "@/components/tools/WikiPanels";

type AuditProfile = {
  character_id: number;
  character_name: string;
  corporation_name: string;
  wallet_balance_isk: string;
  last_sync_at: string | null;
};

type SecurityFlag = {
  id: number;
  character_id: number;
  character_name: string;
  flag_key: string;
  severity: string;
  detail: string;
};

export function AuditAdminWorkspace() {
  const { openWindow, focusWindow } = useWindowManager();
  const [profiles, setProfiles] = useState<AuditProfile[]>([]);
  const [flags, setFlags] = useState<SecurityFlag[]>([]);
  const [assetQ, setAssetQ] = useState("");
  const [assetHits, setAssetHits] = useState<{ character_id: number; type_name: string; quantity: number }[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [wikiTitle, setWikiTitle] = useState<string | null>(null);
  const [wikiWindowTitle, setWikiWindowTitle] = useState("Wiki article");

  const openOrgWiki = useCallback(
    (title: string, displayName: string) => {
      setWikiTitle(title);
      setWikiWindowTitle(displayName);
      openWindow("audit-org-wiki");
      focusWindow("audit-org-wiki");
    },
    [openWindow, focusWindow]
  );

  useEffect(() => {
    void (async () => {
      const [p, f] = await Promise.all([
        fetch("/api/audit/profiles").then((r) => (r.ok ? r.json() : [])),
        fetch("/api/audit/flags").then((r) => (r.ok ? r.json() : [])),
      ]);
      setProfiles(p);
      setFlags(f);
    })();
  }, []);

  const loadDetail = (characterId: number) => {
    setSelected(characterId);
  };

  const searchAssets = async () => {
    if (!assetQ.trim()) return;
    const res = await fetch(`/api/audit/assets/search?q=${encodeURIComponent(assetQ)}`);
    if (res.ok) setAssetHits(await res.json());
  };

  const enqueueSync = async () => {
    await fetch("/api/audit/sync-all/enqueue", { method: "POST" });
  };

  return (
    <CharSheetInspectProvider
      onOpenItemWindow={() => undefined}
      onOpenShipWindow={() => undefined}
      onOpenSystemWindow={() => undefined}
      onOpenWikiWindow={openOrgWiki}
    >
    <WindowDesktop className="min-h-0 flex-1">
      <EveWindow id="audit-admin" title="Member Audit & Asset Index" defaultWidth={900} defaultHeight={560}>
        <div className="grid grid-cols-[1fr_1fr] gap-3 min-h-[420px] text-[11px]">
          <div>
            <div className="flex gap-2 mb-2">
              <button type="button" className="eve-btn-sm eve-btn-primary" onClick={() => void enqueueSync()}>
                Run coalition audit sync
              </button>
            </div>
            <h3 className="text-[var(--accent)] uppercase mb-1">Characters</h3>
            <div className="max-h-[180px] overflow-auto eve-scroll">
              <table className="eve-table w-full">
                <tbody>
                  {profiles.map((p) => (
                    <tr
                      key={p.character_id}
                      className={selected === p.character_id ? "bg-[#12181f]" : "cursor-pointer"}
                      onClick={() => void loadDetail(p.character_id)}
                    >
                      <td>{p.character_name}</td>
                      <td>{p.corporation_name}</td>
                      <td>{Number(p.wallet_balance_isk).toLocaleString()} ISK</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3 className="text-[var(--accent)] uppercase mt-3 mb-1">Security flags</h3>
            <ul className="max-h-[120px] overflow-auto eve-scroll space-y-1">
              {flags.map((f) => (
                <li key={f.id} className={f.severity === "critical" ? "text-[var(--danger)]" : "text-[var(--warn)]"}>
                  {f.character_name}: {f.detail}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-[var(--accent)] uppercase mb-1">Asset search (coalition-wide)</h3>
            <div className="flex gap-2 mb-2">
              <input className="eve-input flex-1" value={assetQ} onChange={(e) => setAssetQ(e.target.value)} placeholder="Module or hull name" />
              <button type="button" className="eve-btn-sm" onClick={() => void searchAssets()}>
                Search
              </button>
            </div>
            <ul className="mb-3 max-h-[100px] overflow-auto eve-scroll">
              {assetHits.map((a, i) => (
                <li key={i}>
                  {a.type_name} ×{a.quantity} — char {a.character_id}
                </li>
              ))}
            </ul>
            <h3 className="text-[var(--accent)] uppercase mb-1">Character detail</h3>
            {selected ? (
              <CharacterSheetPanel characterId={selected} compact />
            ) : (
              <p className="text-[var(--text-muted)]">Select a character to inspect wallet, assets, and alts.</p>
            )}
          </div>
        </div>
      </EveWindow>
      <EveWindow id="audit-org-wiki" title={wikiWindowTitle} defaultWidth={480} defaultHeight={420} defaultX={920} defaultY={80}>
        <WikiArticlePanel
          title={wikiTitle}
          onOpenWiki={(title) => {
            setWikiTitle(title);
            setWikiWindowTitle(title.split("/").pop() || title);
          }}
        />
      </EveWindow>
    </WindowDesktop>
    </CharSheetInspectProvider>
  );
}
