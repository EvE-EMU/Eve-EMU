/** Tranquility image server — https://images.evetech.net */

const EVETECH_IMAGES = "https://images.evetech.net";

/** CDN only serves powers of two from 32px upward; other sizes return HTTP 400. */
export function snapEvetechSize(size: number): number {
  if (size <= 32) return 32;
  let n = 32;
  while (n < size && n < 1024) n *= 2;
  return n;
}

/** EVE type_id 14 = celestial Moon (SDE). */
export const MOON_TYPE_ID = 14;

export type TypeImageMeta = {
  categoryName?: string | null;
  groupName?: string | null;
  /** Skills often 400 on /icon; try /render first when true. */
  preferRender?: boolean;
};

export function isValidEvetechTypeId(typeId: number): boolean {
  return Number.isFinite(typeId) && typeId > 0;
}

export function isBlueprintType(meta?: TypeImageMeta): boolean {
  const category = (meta?.categoryName || "").trim();
  const group = (meta?.groupName || "").trim();
  return category === "Blueprint" || /blueprint/i.test(group);
}

export function typeIconUrl(typeId: number, size = 64) {
  return `${EVETECH_IMAGES}/types/${typeId}/icon?size=${snapEvetechSize(size)}`;
}

export function typeRenderUrl(typeId: number, size = 64) {
  return `${EVETECH_IMAGES}/types/${typeId}/render?size=${snapEvetechSize(size)}`;
}

export function typeBlueprintUrl(typeId: number, size = 64) {
  return `${EVETECH_IMAGES}/types/${typeId}/bp?size=${snapEvetechSize(size)}`;
}

export function typeBlueprintCopyUrl(typeId: number, size = 64) {
  return `${EVETECH_IMAGES}/types/${typeId}/bpc?size=${snapEvetechSize(size)}`;
}

function prefersRenderImage(meta?: TypeImageMeta): boolean {
  if (meta?.preferRender) return true;
  const category = (meta?.categoryName || "").trim();
  if (category === "Skill") return true;
  return /skill/i.test((meta?.groupName || "").trim());
}

/** Ordered image URLs to try; blueprints use bp/bpc instead of icon/render. */
export function typeImageCandidates(typeId: number, size = 64, meta?: TypeImageMeta): string[] {
  if (!isValidEvetechTypeId(typeId)) return [];
  const s = snapEvetechSize(size);
  const base = `${EVETECH_IMAGES}/types/${typeId}`;
  if (isBlueprintType(meta)) {
    return [`${base}/bp?size=${s}`, `${base}/bpc?size=${s}`];
  }
  const icon = `${base}/icon?size=${s}`;
  const render = `${base}/render?size=${s}`;
  return prefersRenderImage(meta) ? [render, icon] : [icon, render];
}

/** BPO scroll icon (original blueprint). */
export function blueprintIconUrl(blueprintTypeId: number, size = 64) {
  return typeBlueprintUrl(blueprintTypeId, size);
}

/** BPO vs BPC — copies (runs >= 0) use the copy scroll art. */
export function blueprintScrollIconUrl(blueprintTypeId: number, runs: number, size = 64) {
  return runs >= 0 ? typeBlueprintCopyUrl(blueprintTypeId, size) : typeBlueprintUrl(blueprintTypeId, size);
}

export function formatBlueprintRuns(runs: number): string {
  if (runs < 0) return "Original";
  if (runs === 0) return "0";
  return String(runs);
}

export function moonIconUrl(size = 64) {
  return typeIconUrl(MOON_TYPE_ID, size);
}

export function characterPortraitUrl(characterId: number, size = 64) {
  return `${EVETECH_IMAGES}/characters/${characterId}/portrait?size=${snapEvetechSize(size)}`;
}

export function corporationLogoUrl(corpId: number, size = 64) {
  return `${EVETECH_IMAGES}/corporations/${corpId}/logo?size=${snapEvetechSize(size)}`;
}

export function allianceLogoUrl(allianceId: number, size = 64) {
  return `${EVETECH_IMAGES}/alliances/${allianceId}/logo?size=${snapEvetechSize(size)}`;
}
