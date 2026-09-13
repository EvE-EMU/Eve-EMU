"use client";

import { useCallback, useEffect } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  IconAdmin,
  IconChevronPanel,
  IconCloseAll,
  IconCommand,
  IconCommerce,
  IconHub,
  IconIndustry,
  IconIntel,
  IconLogOff,
  IconMap,
  IconSde,
  IconSettings,
  IconTemplates,
} from "./icons";
import { Tooltip } from "./Tooltip";
import { AdminGear } from "./AdminGear";
import { useAuth } from "./AuthProvider";
import { useWindowManager } from "./WindowManager";
import { canAccessRoute, ROUTE_ACCESS } from "@/lib/permissions";
import {
  NEOCOM_NAV_GROUPS,
  NEOCOM_SECTIONS,
  countSectionOpenWindows,
  getNavSection,
  groupNavMenuItems,
  sortNavMenuItems,
  windowsForSection,
} from "@/lib/tools/nav";
import { WindowTaskbarIcon } from "@/lib/windowIcons";
import type { NavSectionId } from "@/lib/tools/nav";

type NavItem = {
  id: NavSectionId;
  label: string;
  tip: string;
  icon: typeof IconCommand;
};

const NAV_ICONS: Record<NavSectionId, typeof IconCommand> = {
  activities: IconCommand,
  finance: IconCommerce,
  industry: IconIndustry,
  inventory: IconHub,
  personal: IconIntel,
  ship: IconMap,
  social: IconTemplates,
  "emu-services": IconAdmin,
  utilities: IconSde,
  settings: IconSettings,
};

const NAV_ITEMS: NavItem[] = NEOCOM_SECTIONS.map((section) => ({
  id: section.id,
  label: section.label,
  tip: section.tip,
  icon: NAV_ICONS[section.id],
}));

function NeocomPortrait() {
  const { session } = useAuth();
  const { activeNavSection, neocomPanelOpen, openNavSection } = useWindowManager();

  if (!session.authenticated || !session.character_id) {
    return <div className="eve-neocom-portrait eve-neocom-portrait--guest" aria-hidden />;
  }

  const portraitUrl = `https://images.evetech.net/characters/${session.character_id}/portrait?tenant=tranquility&size=128`;
  const isActive = activeNavSection === "personal";

  return (
    <button
      type="button"
      className={clsx(
        "eve-neocom-portrait",
        isActive && "active",
        isActive && neocomPanelOpen && "eve-neocom-portrait--panel-open"
      )}
      aria-label="Personal"
      title={session.character_name ?? "Personal"}
      onClick={() => openNavSection("personal")}
    >
      <img src={portraitUrl} alt="" className="eve-neocom-portrait-img" />
    </button>
  );
}

function NeocomNavIcon({
  item,
  isActive,
  panelOpen,
  openCount,
}: {
  item: NavItem;
  isActive: boolean;
  panelOpen: boolean;
  openCount: number;
}) {
  const { session } = useAuth();
  const { selectNavSection, launchSection } = useWindowManager();
  const Icon = item.icon;
  const requiredModule = ROUTE_ACCESS[item.id] ?? "public";
  const allowed = canAccessRoute(session, requiredModule);

  const onClick = () => {
    if (!allowed) return;
    selectNavSection(item.id);
  };

  const onDoubleClick = () => {
    if (!allowed) return;
    launchSection(item.id);
  };

  const control = allowed ? (
    <button
      type="button"
      className={clsx(
        "eve-neocom-link",
        isActive && "active",
        isActive && !panelOpen && "eve-neocom-link--panel-closed"
      )}
      aria-label={item.label}
      aria-expanded={isActive && panelOpen}
      aria-current={isActive ? "true" : undefined}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
    >
      <Icon className="h-6 w-6" />
      {openCount > 0 ? (
        <span className="eve-neocom-badge" aria-label={`${openCount} open`}>
          {openCount > 9 ? "9+" : openCount}
        </span>
      ) : null}
    </button>
  ) : (
    <Link
      href={session.login_url || "/api/auth/sso/login"}
      className={clsx("eve-neocom-link", "eve-neocom-link--locked")}
      aria-label={`${item.label} — login required`}
    >
      <Icon className="h-6 w-6 opacity-40" />
    </Link>
  );

  if (allowed) {
    if (panelOpen) {
      return control;
    }
    return (
      <Tooltip label={item.label} hint={`${item.tip} · Double-click opens default`} side="right" className="eve-neocom-tooltip">
        {control}
      </Tooltip>
    );
  }

  if (panelOpen) {
    return control;
  }

  return (
    <Tooltip label={item.label} hint="Login with EVE SSO to access" side="right" className="eve-neocom-tooltip">
      {control}
    </Tooltip>
  );
}

function CloseAllWindowsButton() {
  const { closeAllWindows, windows } = useWindowManager();
  const openCount = windows.filter((w) => w.mode !== "closed").length;

  return (
    <Tooltip
      label="Close all windows"
      hint={openCount > 0 ? `Close ${openCount} open window${openCount === 1 ? "" : "s"}` : "No open windows"}
      side="right"
      className="eve-neocom-tooltip"
    >
      <button
        type="button"
        className="eve-neocom-link eve-neocom-link--close-all"
        aria-label="Close all windows"
        disabled={openCount === 0}
        onClick={closeAllWindows}
      >
        <IconCloseAll className="h-6 w-6" />
      </button>
    </Tooltip>
  );
}

function LogOffButton() {
  const { session } = useAuth();

  if (!session.authenticated) return null;

  const logOff = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/";
  };

  return (
    <Tooltip label="Log off" hint="End your EVE SSO session on EMUMS" side="right" className="eve-neocom-tooltip">
      <button type="button" className="eve-neocom-link eve-neocom-link--logoff" aria-label="Log off" onClick={() => void logOff()}>
        <IconLogOff className="h-6 w-6" />
      </button>
    </Tooltip>
  );
}

function NeocomSidePanel({ sectionId }: { sectionId: string }) {
  const { windows, toggleWindowFromNeocom, focusedWindowId, launchSection, toggleNeocomPanel } =
    useWindowManager();
  const { session } = useAuth();

  const section = getNavSection(sectionId);
  const categoryLabel = section?.label ?? "Tools";
  const registeredIds = new Set(windows.map((w) => w.id));
  const menuItems = sortNavMenuItems(windowsForSection(sectionId, session, registeredIds), windows);
  const menuGroups = groupNavMenuItems(menuItems);
  const defaultEntry = section?.windows.find((w) => w.windowId === section.defaultWindow);

  const openCount = countSectionOpenWindows(sectionId, windows);

  return (
    <div className="eve-neocom-panel-inner">
      <header className="eve-neocom-panel-head">
        <div className="eve-neocom-panel-head-text">
          <span className="eve-neocom-panel-title">{categoryLabel}</span>
          {section?.tip ? <span className="eve-neocom-panel-subtitle">{section.tip}</span> : null}
        </div>
        <Tooltip label="Collapse panel" side="top">
          <button
            type="button"
            className="eve-neocom-panel-collapse"
            aria-label="Collapse neocom panel"
            onClick={toggleNeocomPanel}
          >
            <IconChevronPanel className="h-3.5 w-3.5" />
          </button>
        </Tooltip>
      </header>

      {menuItems.length === 0 ? (
        <p className="eve-neocom-panel-empty">No tools available</p>
      ) : (
        <div className="eve-neocom-panel-list eve-scroll" role="menu">
          {menuGroups.map((group) => (
            <section key={group.label ?? "general"} className="eve-neocom-panel-group">
              {group.label ? (
                <h3 className="eve-neocom-panel-group-title">{group.label}</h3>
              ) : null}
              <ul className="eve-neocom-panel-group-list">
                {group.items.map((item) => {
                  const win = windows.find((w) => w.id === item.windowId);
                  const isOpen = win && win.mode !== "closed";
                  const isFocused =
                    focusedWindowId === item.windowId && isOpen && win?.mode !== "minimized";

                  return (
                    <li key={item.windowId}>
                      <button
                        type="button"
                        className={clsx(
                          "eve-neocom-panel-item",
                          isFocused && "eve-neocom-panel-item--focused",
                          isOpen && !isFocused && "eve-neocom-panel-item--open",
                          win?.mode === "minimized" && "eve-neocom-panel-item--minimized"
                        )}
                        role="menuitem"
                        title={isFocused ? "Click to minimize" : isOpen ? "Click to focus" : "Click to open"}
                        onClick={() => toggleWindowFromNeocom(item.windowId, item.slug)}
                      >
                        <span
                          className={clsx(
                            "eve-neocom-panel-dot",
                            isOpen && `eve-neocom-panel-dot--${win?.mode ?? "open"}`
                          )}
                          aria-hidden
                        />
                        <span className="eve-neocom-panel-icon-slot" aria-hidden>
                          <WindowTaskbarIcon windowId={item.windowId} className="h-3.5 w-3.5" />
                        </span>
                        <span className="eve-neocom-panel-label">{item.label}</span>
                        {win?.mode === "minimized" ? (
                          <span className="eve-neocom-panel-state">Minimized</span>
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}

      {section && defaultEntry ? (
        <footer className="eve-neocom-panel-foot">
          <span className="eve-neocom-panel-foot-meta">
            {openCount > 0 ? `${openCount} open` : "No windows open"}
          </span>
          <button
            type="button"
            className="eve-neocom-panel-foot-btn"
            onClick={() => launchSection(sectionId)}
          >
            Open {defaultEntry.label}
          </button>
        </footer>
      ) : null}
    </div>
  );
}

export function Neocom() {
  const { activeNavSection, neocomPanelOpen, toggleNeocomPanel, openNavSection, windows } =
    useWindowManager();
  const navById = new Map(NAV_ITEMS.map((item) => [item.id, item]));

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && neocomPanelOpen) {
        toggleNeocomPanel();
      }
    },
    [neocomPanelOpen, toggleNeocomPanel]
  );

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKeyDown]);

  return (
    <div className={clsx("eve-neocom-stack", neocomPanelOpen && "eve-neocom-stack--panel-open")}>
      <aside className="eve-neocom-rail flex flex-col">
        <NeocomPortrait />
        <nav className="eve-neocom-nav flex flex-col flex-1 min-h-0 eve-scroll" aria-label="Neocom">
          {NEOCOM_NAV_GROUPS.map((group, groupIndex) => (
            <div key={groupIndex} className="eve-neocom-group">
              {group.sections.map((sectionId) => {
                const item = navById.get(sectionId);
                if (!item) return null;
                return (
                  <NeocomNavIcon
                    key={sectionId}
                    item={item}
                    isActive={activeNavSection === sectionId}
                    panelOpen={neocomPanelOpen}
                    openCount={countSectionOpenWindows(sectionId, windows)}
                  />
                );
              })}
              {groupIndex < NEOCOM_NAV_GROUPS.length - 1 ? <div className="eve-neocom-divider" role="separator" /> : null}
            </div>
          ))}
        </nav>
        <div className="eve-neocom-footer">
          <CloseAllWindowsButton />
          <LogOffButton />
          <AdminGear />
        </div>
      </aside>

      <aside
        className={clsx("eve-neocom-panel", !neocomPanelOpen && "eve-neocom-panel--collapsed")}
        aria-label={`${getNavSection(activeNavSection)?.label ?? "Tools"} menu`}
        aria-hidden={!neocomPanelOpen}
      >
        {neocomPanelOpen ? (
          <NeocomSidePanel sectionId={activeNavSection} />
        ) : (
          <button
            type="button"
            className="eve-neocom-panel-reopen"
            aria-label="Expand neocom panel"
            onClick={() => openNavSection(activeNavSection)}
          >
            <IconChevronPanel className="h-3.5 w-3.5 rotate-180" />
          </button>
        )}
      </aside>
    </div>
  );
}

export function NeocomLocationTitle() {
  const { activeNavSection, focusedWindowId, windows } = useWindowManager();
  const active = NAV_ITEMS.find((n) => n.id === activeNavSection);
  const focused = focusedWindowId ? windows.find((w) => w.id === focusedWindowId) : null;
  const showWindow =
    focused && focused.mode !== "closed" && focused.mode !== "minimized";

  return (
    <>
      <strong>{active?.label ?? "EMU Manager Suite"}</strong>
      {showWindow ? (
        <>
          <span className="text-[var(--text-muted)]">›</span>
          <span className="truncate text-[var(--link-hi)]">{focused.title}</span>
        </>
      ) : null}
    </>
  );
}
