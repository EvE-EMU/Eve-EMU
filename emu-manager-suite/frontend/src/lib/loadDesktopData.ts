import {
  fetchBlueprintContracts,
  fetchCorpMarket,
  fetchDashboard,
  fetchFittings,
  fetchIndyBlueprints,
  fetchIndyCopyRequests,
  fetchIndyIndustryJobs,
  fetchIndustrialProjects,
  fetchIndustrialStructures,
  fetchInvoices,
  fetchJumpShips,
  fetchKillboard,
  fetchMiningLogs,
  fetchMapStatus,
  fetchPniStatements,
  fetchRattingPeriods,
  fetchRoutes,
  fetchHrLeaves,
  fetchSdeCategories,
  fetchSdeSearch,
  fetchServiceLinks,
  fetchSettings,
  fetchSrpLosses,
  fetchStorefront,
  EMPTY_STOREFRONT_CATALOG,
  fetchTaxRules,
  fetchTemplates,
  fetchToolsHub,
} from "@/lib/api";
import { emumsBackendFetch } from "@/lib/bff";

async function fetchAuditFlagsSafe() {
  try {
    const res = await emumsBackendFetch("/audit/flags");
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch {
    return fallback;
  }
}

export async function loadDesktopData() {
  const [
    dash,
    hub,
    corpMarket,
    killboard,
    routes,
    sdeTypes,
    sdeCategories,
    bookmarks,
    jumpShips,
    mapStatus,
    fittings,
    blueprints,
    industryJobs,
    copyRequests,
    projects,
    blueprintContracts,
    storefront,
    structures,
    services,
    ratting,
    leaves,
    pni,
    srp,
    settings,
    taxRules,
    logs,
    invoices,
    templates,
    auditFlags,
  ] = await Promise.all([
    safe(() => fetchDashboard(), null),
    safe(() => fetchToolsHub(), null),
    safe(() => fetchCorpMarket(), []),
    safe(() => fetchKillboard(), []),
    safe(() => fetchRoutes(), []),
    safe(() => fetchSdeSearch("", 500), []),
    safe(() => fetchSdeCategories(), []),
    safe(() => fetchRoutes(), []),
    safe(() => fetchJumpShips(), []),
    safe(() => fetchMapStatus(), null),
    safe(() => fetchFittings(), []),
    safe(() => fetchIndyBlueprints(), []),
    safe(() => fetchIndyIndustryJobs(), []),
    safe(() => fetchIndyCopyRequests(), []),
    safe(() => fetchIndustrialProjects(), []),
    safe(() => fetchBlueprintContracts(), []),
    safe(() => fetchStorefront(), EMPTY_STOREFRONT_CATALOG),
    safe(() => fetchIndustrialStructures(), []),
    safe(() => fetchServiceLinks(), []),
    safe(() => fetchRattingPeriods(), []),
    safe(() => fetchHrLeaves(), []),
    safe(() => fetchPniStatements(), []),
    safe(() => fetchSrpLosses(), []),
    safe(() => fetchSettings(), null),
    safe(() => fetchTaxRules(), []),
    safe(() => fetchMiningLogs(), []),
    safe(() => fetchInvoices(), []),
    safe(() => fetchTemplates(), []),
    fetchAuditFlagsSafe(),
  ]);

  return {
    dash,
    hub,
    corpMarket,
    killboard,
    routes,
    sdeTypes,
    sdeCategories,
    bookmarks,
    jumpShips,
    mapStatus,
    fittings,
    blueprints,
    industryJobs,
    copyRequests,
    projects,
    blueprintContracts,
    storefront,
    structures,
    services,
    ratting,
    leaves,
    pni,
    srp,
    settings,
    taxRules,
    logs,
    invoices,
    templates,
    auditFlags,
  };
}

export type DesktopData = Awaited<ReturnType<typeof loadDesktopData>>;
