/** Map ESI dogma attributes into EVE-style radar chart axes for ships. */

export type RadarPoint = { axis: string; value: number; raw: number; unit?: string };

const SHIP_RADAR_ATTRS: { id: number; axis: string; unit?: string; max?: number }[] = [
  { id: 263, axis: "Shield", max: 50000 },
  { id: 265, axis: "Armor", max: 50000 },
  { id: 9, axis: "Hull", max: 50000 },
  { id: 37, axis: "Speed", max: 5000, unit: "m/s" },
  { id: 50, axis: "Capacitor", max: 10000 },
  { id: 552, axis: "Signature", max: 500, unit: "m" },
  { id: 1240, axis: "Warp", max: 10, unit: "AU/s" },
  { id: 1137, axis: "Cargo", max: 5000, unit: "m³" },
];

function normalize(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0;
  return Math.min(100, Math.round((value / max) * 100));
}

export function shipRadarFromAttributes(
  attributes: { attribute_id: number; name: string; value: number }[]
): RadarPoint[] {
  const byId = new Map(attributes.map((a) => [a.attribute_id, a]));
  const points: RadarPoint[] = [];

  for (const spec of SHIP_RADAR_ATTRS) {
    const attr = byId.get(spec.id);
    if (!attr || attr.value <= 0) continue;
    points.push({
      axis: spec.axis,
      value: normalize(attr.value, spec.max ?? attr.value * 1.2),
      raw: attr.value,
      unit: spec.unit,
    });
  }

  if (points.length >= 3) return points;

  // Fallback: top numeric attributes by magnitude
  const fallback = attributes
    .filter((a) => a.value > 0 && !a.name.toLowerCase().includes("skill"))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
    .map((a) => ({
      axis: a.name.length > 14 ? `${a.name.slice(0, 12)}…` : a.name,
      value: normalize(a.value, a.value),
      raw: a.value,
    }));
  return fallback.length >= 3 ? fallback : points;
}

export function isShipCategory(categoryName?: string, groupName?: string): boolean {
  const cat = (categoryName || "").toLowerCase();
  const grp = (groupName || "").toLowerCase();
  return cat.includes("ship") || grp.includes("frigate") || grp.includes("cruiser") || grp.includes("battleship");
}
