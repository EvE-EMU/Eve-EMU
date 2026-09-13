"use client";

import { AboutWorkspace } from "@/components/AboutWorkspace";
import { DisplaySettingsWindow } from "@/components/DisplaySettingsWindow";
import { MarketBrowserProvider } from "@/components/tools/MarketBrowserContext";
import { MarketBrowserWindows } from "@/components/tools/MarketBrowserWindows";
import { WindowDesktop } from "@/components/WindowManager";
import {
  CommerceWorkspace,
  HubWorkspace,
  IntelligenceWorkspace,
} from "@/components/tools/ToolWorkspaces";
import { IndustrialPlanningWorkspace } from "@/components/tools/IndustrialPlanningWorkspace";
import { SdeWorkspace } from "@/components/tools/SdeWorkspace";
import { MapWorkspace } from "@/components/tools/MapWorkspace";
import { AwesomeSuiteWorkspace } from "@/components/tools/AwesomeSuiteWorkspace";
import { AdministrationDirectorate } from "@/components/AdministrationDirectorate";
import { DashboardWorkspace } from "@/components/DashboardWorkspace";
import { MoonOperations } from "@/components/MoonOperations";
import { SettingsWorkspace } from "@/components/SettingsWorkspace";
import { TemplatesWorkspace } from "@/components/TemplatesWorkspace";
import { PeopleWorkspace } from "@/components/tools/PeopleWorkspace";
import { IdentityAdminPanel } from "@/components/IdentityAdminPanel";
import type { DesktopData } from "@/lib/loadDesktopData";


/** All coalition tool windows on one persistent desktop. */
export function UnifiedDesktop({ data }: { data: DesktopData }) {
  return (
    <WindowDesktop className="min-h-0 flex-1">
      <MarketBrowserProvider>
      <AboutWorkspace />
      <DisplaySettingsWindow />
      <MarketBrowserWindows />
      {data.dash ? <DashboardWorkspace dash={data.dash} embedded /> : null}

      {data.hub ? (
        <>
          <HubWorkspace hub={data.hub} embedded />
          <CommerceWorkspace hub={data.hub} corpMarket={data.corpMarket} embedded />
        </>
      ) : null}

      <IntelligenceWorkspace
        killboard={data.killboard}
        routes={data.routes}
        embedded
      />

      <IndustrialPlanningWorkspace
        fittings={data.fittings}
        blueprints={data.blueprints}
        industryJobs={data.industryJobs}
        copyRequests={data.copyRequests}
        projects={data.projects}
        blueprintContracts={data.blueprintContracts}
        storefront={data.storefront}
        structures={data.structures}
        embedded
      />

      <SdeWorkspace initialTypes={data.sdeTypes} categories={data.sdeCategories} embedded />

      <AwesomeSuiteWorkspace embedded />

      <PeopleWorkspace embedded />
      <IdentityAdminPanel />

      <MapWorkspace
        systems={[]}
        bookmarks={data.bookmarks}
        jumpShips={data.jumpShips}
        mapStatus={data.mapStatus}
        embedded
      />

      {data.settings ? (
        <>
          <MoonOperations
            logs={data.logs}
            invoices={data.invoices}
            settings={data.settings}
            taxRules={data.taxRules}
            embedded
          />
          <SettingsWorkspace
            settings={data.settings}
            taxRules={data.taxRules}
            logs={data.logs}
            invoices={data.invoices}
            embedded
          />
        </>
      ) : null}

      {data.templates.length ? <TemplatesWorkspace templates={data.templates} embedded /> : null}

      {data.services && data.settings ? (
        <AdministrationDirectorate
          services={data.services}
          ratting={data.ratting}
          leaves={data.leaves}
          pni={data.pni}
          srp={data.srp}
          settings={data.settings}
          taxRules={data.taxRules}
          logs={data.logs}
          invoices={data.invoices}
          auditFlags={data.auditFlags}
          embedded
        />
      ) : null}
      </MarketBrowserProvider>
    </WindowDesktop>
  );
}
