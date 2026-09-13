"use client";

import { allianceLogoUrl, corporationLogoUrl } from "@/lib/evetech";
import {
  EVEWHO_FAVICON,
  ZKILL_FAVICON,
  eveWhoAllianceUrl,
  eveWhoCorpUrl,
  wikiAlliancePageTitle,
  wikiCorpPageTitle,
  zKillAllianceUrl,
  zKillCorpUrl,
} from "@/lib/eveTime";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";

const ORG_LOGO_SIZE = 16;
const EXT_ICON_SIZE = Math.round(ORG_LOGO_SIZE / 2);

function OrgExternalLinks({ zkillUrl, eveWhoUrl }: { zkillUrl: string; eveWhoUrl: string }) {
  return (
    <span className="eve-char-sheet-org-ext">
      <a
        href={zkillUrl}
        target="_blank"
        rel="noreferrer"
        className="eve-char-sheet-org-ext-link"
        title="zKillboard"
        aria-label="Open on zKillboard"
      >
        <img src={ZKILL_FAVICON} alt="" width={EXT_ICON_SIZE} height={EXT_ICON_SIZE} className="eve-char-sheet-org-favicon" />
      </a>
      <a
        href={eveWhoUrl}
        target="_blank"
        rel="noreferrer"
        className="eve-char-sheet-org-ext-link"
        title="EveWho"
        aria-label="Open on EveWho"
      >
        <img src={EVEWHO_FAVICON} alt="" width={EXT_ICON_SIZE} height={EXT_ICON_SIZE} className="eve-char-sheet-org-favicon" />
      </a>
    </span>
  );
}

function OrgNameButton({
  name,
  wikiTitle,
  onOpenWiki,
}: {
  name: string;
  wikiTitle: string;
  onOpenWiki?: (title: string, label: string) => void;
}) {
  if (onOpenWiki) {
    return (
      <button type="button" className="eve-char-sheet-org-name" onClick={() => onOpenWiki(wikiTitle, name)}>
        {name}
      </button>
    );
  }
  return <span>{name}</span>;
}

function CorpRow({ corpId, corpName }: { corpId: number; corpName: string }) {
  const inspect = useCharSheetInspect();
  const openWiki = inspect?.openWikiArticle;

  return (
    <span className="eve-char-sheet-org-row">
      <img
        src={corporationLogoUrl(corpId, 32)}
        alt=""
        width={ORG_LOGO_SIZE}
        height={ORG_LOGO_SIZE}
        className="eve-char-sheet-org-logo"
      />
      <OrgNameButton name={corpName} wikiTitle={wikiCorpPageTitle(corpId)} onOpenWiki={openWiki} />
      <OrgExternalLinks zkillUrl={zKillCorpUrl(corpId)} eveWhoUrl={eveWhoCorpUrl(corpId)} />
    </span>
  );
}

function AllianceRow({ allianceId, allianceName }: { allianceId: number; allianceName: string }) {
  const inspect = useCharSheetInspect();
  const openWiki = inspect?.openWikiArticle;

  return (
    <span className="eve-char-sheet-org-row">
      <img
        src={allianceLogoUrl(allianceId, 32)}
        alt=""
        width={ORG_LOGO_SIZE}
        height={ORG_LOGO_SIZE}
        className="eve-char-sheet-org-logo"
      />
      <OrgNameButton name={allianceName} wikiTitle={wikiAlliancePageTitle(allianceId)} onOpenWiki={openWiki} />
      <OrgExternalLinks zkillUrl={zKillAllianceUrl(allianceId)} eveWhoUrl={eveWhoAllianceUrl(allianceId)} />
    </span>
  );
}

export function CharSheetOrgLink({
  corpId,
  corpName,
  allianceId,
  allianceName,
}: {
  corpId?: number;
  corpName?: string;
  allianceId?: number | null;
  allianceName?: string | null;
}) {
  return (
    <div className="eve-char-sheet-org">
      {corpName && corpId ? (
        <CorpRow corpId={corpId} corpName={corpName} />
      ) : corpName ? (
        <span>{corpName}</span>
      ) : null}
      {allianceName && allianceId ? (
        <>
          <span className="eve-char-sheet-sep">·</span>
          <AllianceRow allianceId={allianceId} allianceName={allianceName} />
        </>
      ) : allianceName ? (
        <>
          <span className="eve-char-sheet-sep">·</span>
          <span>{allianceName}</span>
        </>
      ) : null}
    </div>
  );
}
