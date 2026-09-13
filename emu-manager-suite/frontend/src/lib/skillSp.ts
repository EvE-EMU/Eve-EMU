/** EVE Online cumulative skill points at a given trained level. */
export function cumulativeSkillSp(level: number, rank: number): number {
  if (level <= 0 || rank <= 0) return 0;
  let total = 0;
  for (let n = 1; n <= level; n += 1) {
    if (n === 1) {
      total += 250 * rank;
    } else {
      total += 250 * rank * 2 ** ((2 * n - 3) / 2);
    }
  }
  return Math.round(total);
}

export function maxSkillSp(rank: number): number {
  return cumulativeSkillSp(5, rank);
}

export function fmtSp(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
