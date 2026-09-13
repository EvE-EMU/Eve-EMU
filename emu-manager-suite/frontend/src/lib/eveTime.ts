/** EVE time — UTC displayed as YYYY.MM.DD HH:MM */

export function formatEveTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    const h = String(d.getUTCHours()).padStart(2, "0");
    const min = String(d.getUTCMinutes()).padStart(2, "0");
    return `${y}.${m}.${day} ${h}:${min}`;
  } catch {
    return "—";
  }
}

export function eveWhoCorpUrl(corpId: number) {
  return `https://evewho.com/corporation/${corpId}`;
}

export function eveWhoAllianceUrl(allianceId: number) {
  return `https://evewho.com/alliance/${allianceId}`;
}

export function zKillCorpUrl(corpId: number) {
  return `https://zkillboard.com/corporation/${corpId}/`;
}

export function zKillAllianceUrl(allianceId: number) {
  return `https://zkillboard.com/alliance/${allianceId}/`;
}

export function wikiCorpPageTitle(corpId: number) {
  return `Corporations/${corpId}`;
}

export function wikiAlliancePageTitle(allianceId: number) {
  return `Alliances/${allianceId}`;
}

export const ZKILL_FAVICON = "https://zkillboard.com/favicon.ico";
export const EVEWHO_FAVICON = "https://evewho.com/favicon.ico";
