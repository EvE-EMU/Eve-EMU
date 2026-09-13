import type { MoonProductivity } from "@/lib/moonProductivity";
import { DataField, RarityTag, SectionHead } from "./ui";

export function MoonProductivitySummary({
  stats,
  compact = false,
}: {
  stats: MoonProductivity;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "eve-prod-summary eve-prod-summary--compact" : "eve-prod-summary"}>
      <SectionHead>{compact ? "Productivity snapshot" : "Moon productivity"}</SectionHead>
      <div className={compact ? "grid grid-cols-2 gap-x-2" : ""}>
        <DataField label="Avg ISK mined / day" value={`${stats.avgIskMined.toLocaleString()} ISK`} />
        <DataField label="Avg m³ mined / day" value={stats.avgM3Mined.toLocaleString()} />
        <DataField label="Avg pulls / day" value={String(stats.avgPullsPerDay)} />
        <DataField label="Typical mine time" value={`~${stats.typicalMineTimeHours}h`} />
        <DataField
          label="Last jackpot"
          value={`${stats.lastJackpot.isk.toLocaleString()} ISK (${stats.lastJackpot.date})`}
        />
        <DataField
          label="Next extraction"
          value={`${stats.nextExtraction.date} ${stats.nextExtraction.time}`}
        />
        <DataField label="Tax income (moon)" value={`${stats.taxIncome.toLocaleString()} ISK`} />
        {!compact ? (
          <DataField label="Top miner">
            {stats.topMiners[0]
              ? `${stats.topMiners[0].name} (${stats.topMiners[0].corp})`
              : "—"}
          </DataField>
        ) : null}
      </div>
    </div>
  );
}

export function MoonProductivityReport({ stats }: { stats: MoonProductivity }) {
  return (
    <div className="eve-prod-report">
      <div className="flex items-center gap-2 border-b border-[var(--edge-dim)] pb-1.5 mb-1">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-[var(--text)]">{stats.structure}</p>
          <p className="text-[10px] text-[var(--text-muted)]">
            {stats.meta.region} › {stats.meta.system} › {stats.meta.ref}
          </p>
        </div>
        <span className="eve-tag">{stats.meta.moonType}</span>
        {stats.meta.rarity !== "mixed" ? <RarityTag rarity={stats.meta.rarity} /> : null}
      </div>

      <MoonProductivitySummary stats={stats} />

      <div className="mt-1">
        <SectionHead>Extraction cycle</SectionHead>
        <table className="eve-table eve-table-compact">
          <tbody>
            <tr>
              <td className="text-[var(--text-muted)]">Last extraction</td>
              <td>
                {stats.lastExtraction.date} · {stats.lastExtraction.time}
              </td>
            </tr>
            <tr>
              <td className="text-[var(--text-muted)]">Next extraction</td>
              <td className="text-[var(--link-hi)]">
                {stats.nextExtraction.date} · {stats.nextExtraction.time}
              </td>
            </tr>
            <tr>
              <td className="text-[var(--text-muted)]">Last jackpot</td>
              <td>
                {stats.lastJackpot.isk.toLocaleString()} ISK — {stats.lastJackpot.pilot}
              </td>
            </tr>
            <tr>
              <td className="text-[var(--text-muted)]">Avg ISK / pull</td>
              <td className="num">{stats.avgIskPerPull.toLocaleString()}</td>
            </tr>
            <tr>
              <td className="text-[var(--text-muted)]">Avg m³ / pull</td>
              <td className="num">{stats.avgM3PerPull.toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-1">
        <SectionHead>Top corporations</SectionHead>
        <table className="eve-table eve-table-compact">
          <thead>
            <tr>
              <th>Corporation</th>
              <th className="text-right">m³</th>
              <th className="text-right">ISK</th>
              <th className="text-right">Pulls</th>
            </tr>
          </thead>
          <tbody>
            {stats.topCorps.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td className="num">{c.m3.toLocaleString()}</td>
                <td className="num">{c.isk.toLocaleString()}</td>
                <td className="num">{c.pulls}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-1">
        <SectionHead>Top miners</SectionHead>
        <table className="eve-table eve-table-compact">
          <thead>
            <tr>
              <th>Pilot</th>
              <th>Corp</th>
              <th className="text-right">m³</th>
              <th className="text-right">ISK</th>
            </tr>
          </thead>
          <tbody>
            {stats.topMiners.map((m) => (
              <tr key={m.name}>
                <td>{m.name}</td>
                <td className="text-[var(--text-dim)]">{m.corp}</td>
                <td className="num">{m.m3.toLocaleString()}</td>
                <td className="num">{m.isk.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-1">
        <SectionHead>Composition mined</SectionHead>
        <div className="flex flex-wrap gap-1">
          {stats.oreTypes.map((o) => (
            <span key={o} className="eve-tag">
              {o}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
