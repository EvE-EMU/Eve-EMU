"use client";

import { TaxAssessmentsTable } from "@/components/TaxAssessmentsTable";
import {
  InvoiceStatusChart,
  MiningAreaChart,
  RarityPieChart,
  StructureBarChart,
} from "@/components/Charts";
import { EveWindow, KpiStrip, KpiTile, StatusStrip } from "@/components/ui";
import { DesktopSurface } from "@/components/WindowManager";
import type { Dashboard } from "@/lib/api";

export function DashboardWorkspace({ dash, embedded }: { dash: Dashboard; embedded?: boolean }) {
  const windows = (
    <>
        <EveWindow
          id="extraction-volume"
          title="Extraction Volume"
          defaultX={4}
          defaultY={4}
          defaultWidth={520}
          defaultHeight={220}
        >
          <MiningAreaChart data={dash.mining_by_day} />
        </EveWindow>
        <EveWindow
          id="rarity-mix"
          title="Rarity Mix"
          defaultX={532}
          defaultY={4}
          defaultWidth={300}
          defaultHeight={220}
        >
          <RarityPieChart data={dash.rarity_mix} />
        </EveWindow>
        <EveWindow
          id="structure-output"
          title="Structure Output"
          defaultX={4}
          defaultY={232}
          defaultWidth={400}
          defaultHeight={240}
        >
          <StructureBarChart data={dash.top_structures} />
        </EveWindow>
        <EveWindow
          id="invoice-status"
          title="Invoice Status"
          defaultX={412}
          defaultY={232}
          defaultWidth={420}
          defaultHeight={240}
        >
          <InvoiceStatusChart data={dash.invoice_status} />
        </EveWindow>
        <EveWindow
          id="recent-tax"
          title="Recent Tax Assessments"
          defaultX={4}
          defaultY={480}
          defaultWidth={640}
          defaultHeight={240}
        >
          <TaxAssessmentsTable invoices={dash.recent_invoices} />
        </EveWindow>
    </>
  );

  if (embedded) return windows;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <StatusStrip>{dash.tagline}</StatusStrip>
      <KpiStrip>
        {dash.kpis.map((k) => (
          <KpiTile key={k.label} label={k.label} value={k.value} tone={k.tone} />
        ))}
      </KpiStrip>
      <DesktopSurface className="min-h-0 flex-1">{windows}</DesktopSurface>
    </div>
  );
}
