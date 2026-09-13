"use client";

import { useMemo, useState } from "react";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { formatEveTime } from "@/lib/eveTime";
import { maxSkillSp, fmtSp, cumulativeSkillSp } from "@/lib/skillSp";

export type CharacterSkillRow = {
  skill_type_id: number;
  skill_name: string;
  skill_group?: string;
  trained_level: number;
  active_level?: number;
  skill_rank?: number;
  skillpoints_in_skill?: number;
  max_skillpoints?: number;
  is_training?: boolean;
};

export type SkillQueueRow = {
  skill_type_id: number;
  skill_name: string;
  finished_level: number;
  queue_position: number;
  finish_date?: string | null;
  start_date?: string | null;
};

type SkillSort = "level" | "name";

function SkillLevelPips({
  trained,
  active,
  isTraining,
}: {
  trained: number;
  active: number;
  isTraining?: boolean;
}) {
  const pips = [];
  for (let level = 1; level <= 5; level += 1) {
    let state: "empty" | "half" | "full" = "empty";
    if (trained >= level) {
      state = "full";
    } else if (level === trained + 1 && (active > trained || isTraining)) {
      state = "half";
    }
    pips.push(
      <span
        key={level}
        className={`eve-skill-pip eve-skill-pip--${state}`}
        title={`Level ${level}`}
        aria-hidden
      />
    );
  }
  return (
    <span className="eve-skill-pips" aria-label={`Skill level ${trained}${isTraining ? ", training" : ""}`}>
      {pips}
    </span>
  );
}

function sortSkills(rows: CharacterSkillRow[], sort: SkillSort): CharacterSkillRow[] {
  const copy = [...rows];
  if (sort === "name") {
    copy.sort((a, b) => a.skill_name.localeCompare(b.skill_name));
  } else {
    copy.sort((a, b) => b.trained_level - a.trained_level || a.skill_name.localeCompare(b.skill_name));
  }
  return copy;
}

function SkillQueuePanel({ queue }: { queue: SkillQueueRow[] }) {
  const ordered = useMemo(
    () => [...queue].sort((a, b) => a.queue_position - b.queue_position),
    [queue]
  );

  return (
    <aside className="eve-char-sheet-skill-queue-panel">
      <h3 className="eve-char-sheet-section-title">Skill queue</h3>
      {ordered.length ? (
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th />
              <th>Skill</th>
              <th>To</th>
              <th>Completes</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((row, index) => (
              <tr key={`${row.skill_type_id}-${row.queue_position}`} className={index === 0 ? "training" : ""}>
                <td className="w-6">
                  <EveTypeIcon typeId={row.skill_type_id} size={18} preferRender categoryName="Skill" />
                </td>
                <td>
                  {row.skill_name}
                  {index === 0 ? <span className="eve-char-sheet-training-tag">Now</span> : null}
                </td>
                <td className="tabular-nums w-8">{row.finished_level}</td>
                <td className="whitespace-nowrap text-[var(--text-muted)]">
                  {formatEveTime(row.finish_date)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-[var(--text-muted)]">Queue empty.</p>
      )}
    </aside>
  );
}

export function CharacterSheetSkills({
  skills,
  skillQueue = [],
}: {
  skills: CharacterSkillRow[];
  skillQueue?: SkillQueueRow[];
}) {
  const [skillQ, setSkillQ] = useState("");
  const [sort, setSort] = useState<SkillSort>("level");
  const [hideUntrained, setHideUntrained] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const grouped = useMemo(() => {
    const q = skillQ.trim().toLowerCase();
    let rows = skills;
    if (hideUntrained) {
      rows = rows.filter((s) => s.trained_level > 0);
    }
    const filtered = q
      ? rows.filter(
          (s) =>
            s.skill_name.toLowerCase().includes(q) ||
            (s.skill_group || "Other").toLowerCase().includes(q)
        )
      : rows;

    const buckets = new Map<string, CharacterSkillRow[]>();
    for (const row of filtered) {
      const group = row.skill_group || "Other";
      const list = buckets.get(group) ?? [];
      list.push(row);
      buckets.set(group, list);
    }

    return [...buckets.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([group, groupRows]) => {
        let trainedSp = 0;
        let maxSp = 0;
        for (const row of groupRows) {
          const rank = row.skill_rank ?? 1;
          const maxRowSp = row.max_skillpoints ?? maxSkillSp(rank);
          maxSp += maxRowSp;
          if (row.trained_level > 0) {
            trainedSp += row.skillpoints_in_skill || cumulativeSkillSp(row.trained_level, rank);
          }
        }
        const trainedCount = groupRows.filter((s) => s.trained_level > 0).length;
        return {
          group,
          trainedCount,
          totalCount: groupRows.length,
          trainedSp,
          maxSp,
          rows: sortSkills(groupRows, sort),
        };
      });
  }, [skills, skillQ, sort, hideUntrained]);

  const toggleGroup = (group: string) => {
    setCollapsed((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  const isCollapsed = (group: string) => collapsed[group] ?? true;

  return (
    <div className="eve-char-sheet-skills">
      <div className="eve-char-sheet-skills-toolbar">
        <input
          className="eve-input flex-1 max-w-xs"
          placeholder="Filter skills…"
          value={skillQ}
          onChange={(e) => setSkillQ(e.target.value)}
        />
        <div className="eve-char-sheet-sort" role="group" aria-label="Sort skills">
          <span className="eve-char-sheet-sort-label">Sort</span>
          <button type="button" className={sort === "level" ? "active" : ""} onClick={() => setSort("level")}>
            Level
          </button>
          <button type="button" className={sort === "name" ? "active" : ""} onClick={() => setSort("name")}>
            Name
          </button>
        </div>
        <label className="eve-char-sheet-check flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
          <input type="checkbox" checked={hideUntrained} onChange={(e) => setHideUntrained(e.target.checked)} />
          Hide untrained
        </label>
      </div>

      <div className="eve-char-sheet-skills-split">
        <div className="eve-char-sheet-skill-groups eve-char-sheet-skill-groups--narrow">
          {grouped.length ? (
            grouped.map(({ group, rows, trainedCount, totalCount, trainedSp, maxSp }) => {
              const closed = isCollapsed(group);
              const spPct = maxSp > 0 ? Math.min(100, Math.round((trainedSp / maxSp) * 100)) : 0;
              return (
                <section key={group} className="eve-char-sheet-skill-group">
                  <button
                    type="button"
                    className="eve-char-sheet-skill-group-head"
                    aria-expanded={!closed}
                    onClick={() => toggleGroup(group)}
                  >
                    <span className={`eve-char-sheet-chevron ${closed ? "" : "open"}`} aria-hidden />
                    <span className="eve-char-sheet-skill-group-title">{group}</span>
                    <span className="eve-char-sheet-skill-group-sp">
                      {fmtSp(trainedSp)} / {fmtSp(maxSp)}
                    </span>
                    <span className="eve-char-sheet-skill-group-count">
                      {trainedCount}/{totalCount}
                    </span>
                  </button>
                  <div
                    className="eve-char-sheet-skill-group-progress"
                    role="progressbar"
                    aria-valuenow={spPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    title={`${fmtSp(trainedSp)} of ${fmtSp(maxSp)} SP in this group`}
                  >
                    <span className="eve-char-sheet-skill-group-progress-fill" style={{ width: `${spPct}%` }} />
                  </div>
                  {!closed ? (
                    <table className="eve-table w-full text-[10px]">
                      <tbody>
                        {rows.map((s) => (
                          <tr
                            key={s.skill_type_id}
                            className={`${s.is_training ? "training" : ""}${s.trained_level <= 0 ? " untrained" : ""}`}
                          >
                            <td className="w-6">
                              <EveTypeIcon
                                typeId={s.skill_type_id}
                                size={18}
                                preferRender
                                categoryName="Skill"
                              />
                            </td>
                            <td className="truncate max-w-[140px]" title={s.skill_name}>
                              {s.skill_name}
                              {s.is_training ? (
                                <span className="eve-char-sheet-training-tag">Training</span>
                              ) : null}
                            </td>
                            <td className="w-24">
                              <SkillLevelPips
                                trained={s.trained_level}
                                active={s.active_level ?? s.trained_level}
                                isTraining={s.is_training}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : null}
                </section>
              );
            })
          ) : (
            <p className="text-[var(--text-muted)]">No skills match your filter.</p>
          )}
        </div>
        <SkillQueuePanel queue={skillQueue} />
      </div>
    </div>
  );
}

export function SkillLevelPipsCompact(props: {
  trained: number;
  active?: number;
  isTraining?: boolean;
}) {
  return (
    <SkillLevelPips
      trained={props.trained}
      active={props.active ?? props.trained}
      isTraining={props.isTraining}
    />
  );
}
