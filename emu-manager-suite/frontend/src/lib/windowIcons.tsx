/** Taskbar icons for minimized windows — keyed by EveWindow id. */

import type { ComponentType } from "react";
import {
  IconAdmin,
  IconCommerce,
  IconCommand,
  IconHub,
  IconIndustry,
  IconIntel,
  IconMap,
  IconMoons,
  IconSde,
  IconSettings,
  IconTemplates,
} from "@/components/icons";

type IconProps = { className?: string };

const WINDOW_ICON_MAP: Record<string, ComponentType<IconProps>> = {
  "tools-hub": IconHub,
  "authed-structures": IconHub,
  buyback: IconCommerce,
  appraisal: IconCommerce,
  "refine-calc": IconCommerce,
  "market-watch": IconCommerce,
  "market-browser": IconCommerce,
  "market-stations": IconCommerce,
  "corp-market": IconCommerce,
  "char-audit": IconIntel,
  "interaction-audit": IconIntel,
  "webhook-alerts": IconSettings,
  "char-item-detail": IconSde,
  "char-ship-fitting": IconIndustry,
  killboard: IconIntel,
  "route-planner": IconMap,
  "sde-browser": IconSde,
  "sde-detail": IconSde,
  "sde-compare": IconSde,
  "suite-hub": IconHub,
  "suite-intel": IconIntel,
  "suite-trade": IconCommerce,
  "suite-corpwho": IconIntel,
  "suite-br": IconIntel,
  "suite-skills": IconIntel,
  "suite-gatecamp": IconMap,
  "suite-haul": IconCommerce,
  "suite-structures": IconHub,
  "suite-ships": IconIndustry,
  "suite-insurance": IconCommerce,
  "structure-fuel": IconHub,
  "moon-timing": IconMoons,
  "wiki-article": IconSde,
  "map-planner": IconMap,
  "map-visual": IconMap,
  "jump-range": IconMap,
  fittings: IconIndustry,
  "ip-planner": IconIndustry,
  "pi-overview": IconIndustry,
  "ip-blueprints": IconIndustry,
  "ip-projects": IconIndustry,
  "ip-jobs": IconIndustry,
  "ip-storefront": IconIndustry,
  "indy-blueprints": IconIndustry,
  "indy-jobs": IconIndustry,
  "indy-copy": IconIndustry,
  "mat-exchange": IconIndustry,
  "industry-calc": IconIndustry,
  "indy-hub": IconIndustry,
  services: IconAdmin,
  onboarding: IconAdmin,
  "admission-rank": IconAdmin,
  "standings-sync": IconIntel,
  "ops-calendar": IconCommand,
  "identity-rbac": IconSettings,
  "ratting-tax": IconAdmin,
  "hr-directorate": IconAdmin,
  "pni-statements": IconAdmin,
  "srp-program": IconAdmin,
  "org-settings": IconSettings,
  "display-settings": IconSettings,
  "admin-users": IconSettings,
  "ops-tagline": IconSettings,
  "moon-ops": IconMoons,
  "moon-invoices": IconMoons,
  "moon-tax": IconMoons,
  templates: IconTemplates,
};

function IconWindow({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="2" y="3" width="12" height="10" />
      <path d="M2 5.5h12" />
    </svg>
  );
}

export function WindowTaskbarIcon({ windowId, className }: { windowId: string; className?: string }) {
  const Icon = WINDOW_ICON_MAP[windowId] ?? IconCommand;
  return <Icon className={className ?? "h-3.5 w-3.5 shrink-0"} />;
}

export function windowIconForId(windowId: string): ComponentType<IconProps> {
  return WINDOW_ICON_MAP[windowId] ?? IconWindow;
}
