"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EveWindow } from "@/components/ui";
import { DesktopSurface, useWindowManagerOptional } from "@/components/WindowManager";
import { KpiStrip, KpiTile, SectionHead, StatusStrip } from "@/components/ui";
import { BuildPlannerPanel } from "@/components/tools/BuildPlannerPanel";
import { IndustryJobsPanel } from "@/components/tools/IndustryJobsPanel";
import { StorefrontPanel } from "@/components/tools/StorefrontPanel";
import { blueprintScrollIconUrl, formatBlueprintRuns } from "@/lib/evetech";

type FittingRow = Awaited<ReturnType<typeof import("@/lib/api").fetchFittings>>[number];
type BlueprintRow = Awaited<ReturnType<typeof import("@/lib/api").fetchIndyBlueprints>>[number];

function fmtIsk(v: string | number | null | undefined) {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}


export function IndustrialPlanningWorkspace(props: {
  fittings: Awaited<ReturnType<typeof import("@/lib/api").fetchFittings>>;
  blueprints: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyBlueprints>>;
  industryJobs: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyIndustryJobs>>;
  copyRequests: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyCopyRequests>>;
  projects: Awaited<ReturnType<typeof import("@/lib/api").fetchIndustrialProjects>>;
  blueprintContracts: Awaited<ReturnType<typeof import("@/lib/api").fetchBlueprintContracts>>;
  storefront: Awaited<ReturnType<typeof import("@/lib/api").fetchStorefront>>;
  structures: Awaited<ReturnType<typeof import("@/lib/api").fetchIndustrialStructures>>;
  embedded?: boolean;
}) {
  return (
    <Suspense fallback={null}>
      <IndustrialPlanningWorkspaceInner {...props} />
    </Suspense>
  );
}

function IndustrialPlanningWorkspaceInner({
  fittings,
  blueprints,
  industryJobs,
  copyRequests,
  projects,
  blueprintContracts,
  storefront,
  structures,
  embedded,
}: {
  fittings: Awaited<ReturnType<typeof import("@/lib/api").fetchFittings>>;
  blueprints: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyBlueprints>>;
  industryJobs: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyIndustryJobs>>;
  copyRequests: Awaited<ReturnType<typeof import("@/lib/api").fetchIndyCopyRequests>>;
  projects: Awaited<ReturnType<typeof import("@/lib/api").fetchIndustrialProjects>>;
  blueprintContracts: Awaited<ReturnType<typeof import("@/lib/api").fetchBlueprintContracts>>;
  storefront: Awaited<ReturnType<typeof import("@/lib/api").fetchStorefront>>;
  structures: Awaited<ReturnType<typeof import("@/lib/api").fetchIndustrialStructures>>;
  embedded?: boolean;
}) {
  const searchParams = useSearchParams();
  const highlightTypeId = Number(searchParams.get("type_id") || "") || null;
  const wm = useWindowManagerOptional();
  const [bpTab, setBpTab] = useState<"library" | "contracts" | "requests">("library");
  const [bpScope, setBpScope] = useState<"all" | "personal" | "corp">("all");
  const [liveFittings, setLiveFittings] = useState<FittingRow[]>(fittings);
  const [liveBlueprints, setLiveBlueprints] = useState<BlueprintRow[]>(blueprints);
  const [liveJobs, setLiveJobs] = useState(industryJobs);
  const [industrySyncing, setIndustrySyncing] = useState(false);
  const [industryLoadError, setIndustryLoadError] = useState<string | null>(null);
  const [plannerBlueprintId, setPlannerBlueprintId] = useState<number | null>(null);

  const loadIndustryData = useCallback(async () => {
    setIndustryLoadError(null);
    try {
      const [fRes, bRes, jRes] = await Promise.all([
        fetch("/api/tools/industry/fittings", { cache: "no-store" }),
        fetch("/api/tools/industry/blueprints", { cache: "no-store" }),
        fetch("/api/tools/industry/jobs", { cache: "no-store" }),
      ]);
      if (fRes.ok) setLiveFittings(await fRes.json());
      if (bRes.ok) setLiveBlueprints(await bRes.json());
      if (jRes.ok) setLiveJobs(await jRes.json());
      if (!fRes.ok && !bRes.ok && !jRes.ok) {
        setIndustryLoadError("Log in via SSO to load in-game fittings and blueprints.");
      }
    } catch {
      setIndustryLoadError("Could not load industry data.");
    }
  }, []);

  useEffect(() => {
    void loadIndustryData();
  }, [loadIndustryData]);

  const syncIndustry = useCallback(async () => {
    setIndustrySyncing(true);
    setIndustryLoadError(null);
    try {
      const res = await fetch("/api/tools/industry/sync", { method: "POST", cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err =
          typeof data?.detail === "string"
            ? data.detail
            : data?.scope_errors
              ? Object.values(data.scope_errors as Record<string, string>).join(" · ")
              : "Sync failed — re-authorize SSO if scopes changed.";
        setIndustryLoadError(err);
        return;
      }
      const warnings = data?.scope_errors
        ? Object.values(data.scope_errors as Record<string, string>).filter(Boolean).join(" · ")
        : "";
      if (warnings) setIndustryLoadError(warnings);
      await loadIndustryData();
    } finally {
      setIndustrySyncing(false);
    }
  }, [loadIndustryData]);

  const filteredBps =
    bpScope === "all" ? liveBlueprints : liveBlueprints.filter((b) => b.owner_scope === bpScope);

  const openBlueprintInPlanner = useCallback(
    (blueprintId: number) => {
      setPlannerBlueprintId(blueprintId);
      if (!wm) return;
      wm.openWindow("ip-planner");
      wm.focusWindow("ip-planner");
      const win = wm.windows.find((w) => w.id === "ip-planner");
      if (win) {
        wm.setBounds(
          "ip-planner",
          win.x,
          win.y,
          Math.max(win.width, 920),
          Math.max(win.height ?? 760, 760)
        );
      }
    },
    [wm]
  );

  const openCopy = copyRequests.filter((c) => c.status === "open" || c.status === "offered").length;

  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <div className="mx-2 mb-2 rounded border border-[var(--edge-dim)] bg-[var(--bg-raised)] px-3 py-2 text-[11px] leading-snug text-[var(--text-muted)]">
        <strong className="text-[var(--text)]">Deprecated parallel UX</strong> — the canonical
        industrial product is{" "}
        <a
          className="text-[var(--accent)] underline"
          href="https://eve-emu.com/industrial"
          target="_blank"
          rel="noreferrer"
        >
          eve-emu.com/industrial
        </a>{" "}
        (Plan / Orders / Ops / Tools). Storefront checkout already bridges to ManufacturingProject
        quotes; prefer Nidavellir + Orders board for new work.
        <div className="mt-1.5 flex flex-wrap gap-2">
          <a className="eve-btn eve-btn-primary" href="https://eve-emu.com/industrial?tab=forge">
            Open Plan (Nidavellir)
          </a>
          <a className="eve-btn" href="https://eve-emu.com/industrial?tab=projects">
            Orders board
          </a>
          <a className="eve-btn" href="https://eve-emu.com/industrial?tab=market">
            Market / storefront
          </a>
        </div>
      </div>
      <EveWindow
        id="ip-planner"
        title="Industrial Planning — Build Planner (legacy)"
        defaultX={16}
        defaultY={16}
        defaultWidth={920}
        defaultHeight={760}
      >
        <BuildPlannerPanel
          fittings={liveFittings}
          blueprints={liveBlueprints}
          structures={structures}
          projects={projects}
          onSync={() => void syncIndustry()}
          syncing={industrySyncing}
          syncError={industryLoadError}
          focusBlueprintId={plannerBlueprintId}
          onFocusBlueprintHandled={() => setPlannerBlueprintId(null)}
        />
      </EveWindow>

      <EveWindow
        id="ip-blueprints"
        title="Blueprints & Contracts"
        defaultX={588}
        defaultY={16}
        defaultWidth={560}
        defaultHeight={620}
      >
        <div className="flex flex-col min-h-0 h-full">
          <StatusStrip>Browse your prints, request copies, or shop public blueprint contracts</StatusStrip>
        <div className="flex flex-wrap gap-1 mb-2">
          {(["library", "contracts", "requests"] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={`eve-btn ${bpTab === t ? "eve-btn-primary" : ""}`}
              onClick={() => setBpTab(t)}
            >
              {t === "library" ? "My BPs" : t === "contracts" ? "Public contracts" : "Copy requests"}
            </button>
          ))}
        </div>

        {bpTab === "library" ? (
          <>
            <div className="flex gap-1 mb-2">
              {(["all", "personal", "corp"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`eve-btn ${bpScope === s ? "eve-btn-primary" : ""}`}
                  onClick={() => setBpScope(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="flex-1 min-h-0 overflow-auto eve-scroll mt-1">
            <table className="eve-table">
              <thead>
                <tr>
                  <th />
                  <th>Blueprint</th>
                  <th>Runs</th>
                  <th>Location</th>
                  <th>ME/TE</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredBps.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <img
                        src={blueprintScrollIconUrl(b.type_id, b.runs, 32)}
                        alt=""
                        width={24}
                        height={24}
                      />
                    </td>
                    <td>{b.type_name}</td>
                    <td className="num text-[10px]">{formatBlueprintRuns(b.runs)}</td>
                    <td className="text-[var(--text-muted)]">{b.location_name}</td>
                    <td className="num">
                      {b.material_efficiency}/{b.time_efficiency}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="eve-btn-sm"
                        onClick={() => openBlueprintInPlanner(b.id)}
                      >
                        Build Planner →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        ) : null}

        {bpTab === "contracts" ? (
          <div className="flex-1 min-h-0 overflow-auto eve-scroll mt-1">
          <table className="eve-table">
            <thead>
              <tr>
                <th>Blueprint</th>
                <th>Seller</th>
                <th>Location</th>
                <th>Runs</th>
                <th>ME/TE</th>
                <th className="text-right">Price</th>
              </tr>
            </thead>
            <tbody>
              {blueprintContracts.map((c) => (
                <tr key={c.id}>
                  <td>{c.blueprint_name}</td>
                  <td>{c.seller_name}</td>
                  <td>{c.location}</td>
                  <td className="num">{formatBlueprintRuns(c.runs)}</td>
                  <td className="num">
                    {c.material_efficiency}/{c.time_efficiency}
                  </td>
                  <td className="num">{fmtIsk(c.price_isk)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        ) : null}

        {bpTab === "requests" ? (
          <>
            <KpiStrip>
              <KpiTile label="Open" value={String(openCopy)} tone="warn" />
            </KpiStrip>
            <table className="eve-table mt-1">
              <thead>
                <tr>
                  <th>Requester</th>
                  <th>Blueprint</th>
                  <th>Runs</th>
                  <th>Status</th>
                  <th>Assignee</th>
                </tr>
              </thead>
              <tbody>
                {copyRequests.map((c) => (
                  <tr key={c.id}>
                    <td>{c.requester}</td>
                    <td>{c.blueprint_name}</td>
                    <td className="num">{c.runs}</td>
                    <td>{c.status}</td>
                    <td>{c.assignee || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
        </div>
      </EveWindow>

      <EveWindow
        id="ip-projects"
        title="Project Costing"
        defaultX={16}
        defaultY={548}
        defaultWidth={560}
        defaultHeight={320}
      >
        <StatusStrip>
          Assign stock to a named container with a project ID — track materials and jobs for true build cost
        </StatusStrip>
        {projects.map((p) => (
          <div key={p.id} className="border border-[var(--edge-dim)] p-2 mb-2">
            <div className="flex flex-wrap gap-2 items-baseline">
              <strong>{p.project_code}</strong>
              <span>{p.name}</span>
              <span className="text-[var(--text-muted)]">Container: {p.container_name}</span>
            </div>
            <KpiStrip>
              <KpiTile label="Materials" value={`${fmtIsk(p.material_cost_isk)} ISK`} />
              <KpiTile label="Jobs" value={`${fmtIsk(p.job_cost_isk)} ISK`} />
              <KpiTile label="True cost" value={`${fmtIsk(p.true_cost_isk)} ISK`} tone="ok" />
            </KpiStrip>
            {p.stock_lines.length > 0 ? (
              <table className="eve-table mt-1">
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>Qty</th>
                    <th className="text-right">Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {p.stock_lines.map((s, i) => (
                    <tr key={i}>
                      <td>{s.type_name}</td>
                      <td className="num">{s.quantity.toLocaleString()}</td>
                      <td className="num">{fmtIsk(s.unit_cost_isk)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {p.job_lines.length > 0 ? (
              <table className="eve-table mt-1">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Runs</th>
                    <th className="text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {p.job_lines.map((j, i) => (
                    <tr key={i}>
                      <td>{j.description}</td>
                      <td className="num">{j.runs}</td>
                      <td className="num">{fmtIsk(j.cost_isk)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        ))}
      </EveWindow>

      <EveWindow
        id="ip-jobs"
        title="Industry Jobs"
        defaultX={588}
        defaultY={548}
        defaultWidth={720}
        defaultHeight={480}
      >
        <IndustryJobsPanel
          jobs={liveJobs}
          onSync={() => void syncIndustry()}
          syncing={industrySyncing}
          syncError={industryLoadError}
          onRefresh={() => void loadIndustryData()}
        />
      </EveWindow>

      <EveWindow
        id="ip-storefront"
        title="Storefront"
        defaultX={1088}
        defaultY={16}
        defaultWidth={720}
        defaultHeight={852}
      >
        <StorefrontPanel catalog={storefront} highlightTypeId={highlightTypeId} />
      </EveWindow>
    </DesktopSurface>
  );
}
