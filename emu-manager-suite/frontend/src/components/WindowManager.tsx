"use client";

import {
  createContext,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import clsx from "clsx";
import {
  consumePendingNotificationFocus,
  peekPendingNotificationFocus,
} from "@/lib/notifications/navigation";
import {
  DESKTOP_ROUTE,
  layoutWithClosedModes,
  loadWindowLayout,
  maxZIndex,
  saveWindowLayout,
} from "@/lib/windowLayoutStorage";
import { NAV_LAUNCH_WINDOWS, WINDOW_NAV_SECTION } from "@/lib/desktop";
import { getNavSection } from "@/lib/tools/nav";
import { syncDesktopUrl, openToolInDesktop } from "@/lib/openTool";
import { loadNeocomPrefs, saveNeocomPrefs } from "@/lib/neocomStorage";
import { WindowTaskbarIcon } from "@/lib/windowIcons";
import { TOOLS } from "@/lib/tools/registry";

function resolveToolWindowId(tool: string): string {
  const def = TOOLS.find((t) => t.slug === tool || t.windowId === tool);
  return def?.windowId ?? tool;
}

export type WindowMode = "open" | "minimized" | "maximized" | "closed";

export type WindowRegistration = {
  id: string;
  title: string;
  defaultX?: number;
  defaultY?: number;
  defaultWidth?: number;
  defaultHeight?: number;
};

export type WindowState = {
  id: string;
  title: string;
  mode: WindowMode;
  x: number;
  y: number;
  width: number;
  height: number | null;
  zIndex: number;
  restoreX?: number;
  restoreY?: number;
  restoreWidth?: number;
  restoreHeight?: number | null;
};

type RouteWindows = Record<string, WindowState>;

type WindowManagerContextValue = {
  route: string;
  windows: WindowState[];
  activeNavSection: string;
  neocomPanelOpen: boolean;
  focusedWindowId: string | null;
  taskbarReserve: number;
  registerWindow: (reg: WindowRegistration) => void;
  unregisterWindow: (id: string) => void;
  setMode: (id: string, mode: WindowMode) => void;
  setPosition: (id: string, x: number, y: number) => void;
  setBounds: (id: string, x: number, y: number, width: number, height: number) => void;
  focusWindow: (id: string) => void;
  openWindow: (id: string) => void;
  launchSection: (navSectionId: string, windowId?: string) => void;
  selectNavSection: (navSectionId: string) => void;
  openNavSection: (navSectionId: string) => void;
  toggleWindowFromNeocom: (windowId: string, slug?: string) => void;
  toggleNeocomPanel: () => void;
  setNeocomPanelOpen: (open: boolean) => void;
  minimizeWindow: (id: string) => void;
  maximizeWindow: (id: string) => void;
  restoreWindow: (id: string) => void;
  closeAllWindows: () => void;
  desktopRef: React.RefObject<HTMLDivElement | null>;
};

const WindowManagerContext = createContext<WindowManagerContextValue | null>(null);

const TITLEBAR_H = 22;

function staggerPosition(index: number) {
  return { x: 8 + (index % 3) * 24, y: 8 + (index % 4) * 22 };
}

function pickTopFocusableWindow(windows: WindowState[], excludeId?: string): string | null {
  const candidates = windows.filter(
    (w) => w.id !== excludeId && (w.mode === "open" || w.mode === "maximized")
  );
  if (!candidates.length) return null;
  return candidates.reduce((a, b) => (a.zIndex >= b.zIndex ? a : b)).id;
}

export function WindowManagerProvider({ children }: { children: ReactNode }) {
  const desktopRef = useRef<HTMLDivElement | null>(null);
  const [byRoute, setByRoute] = useState<Record<string, RouteWindows>>({});
  const [activeNavSection, setActiveNavSection] = useState("personal");
  const [neocomPanelOpen, setNeocomPanelOpen] = useState(true);
  const [focusedWindowId, setFocusedWindowId] = useState<string | null>(null);
  const [layoutHydrated, setLayoutHydrated] = useState(false);
  const [neocomPrefsHydrated, setNeocomPrefsHydrated] = useState(false);
  const registerCounterRef = useRef(0);
  const zCounterRef = useRef(10);

  useEffect(() => {
    const prefs = loadNeocomPrefs();
    setActiveNavSection(prefs.activeSection);
    setNeocomPanelOpen(prefs.panelOpen);
    setNeocomPrefsHydrated(true);
  }, []);

  useEffect(() => {
    if (!neocomPrefsHydrated) return;
    saveNeocomPrefs({ panelOpen: neocomPanelOpen, activeSection: activeNavSection });
  }, [neocomPanelOpen, activeNavSection, neocomPrefsHydrated]);

  useEffect(() => {
    const layout = loadWindowLayout();
    setByRoute(layout);
    zCounterRef.current = maxZIndex(layout);
    setLayoutHydrated(true);
  }, []);

  useEffect(() => {
    if (!layoutHydrated) return;
    saveWindowLayout(
      layoutWithClosedModes({ [DESKTOP_ROUTE]: byRoute[DESKTOP_ROUTE] ?? {} })
    );
  }, [byRoute, layoutHydrated]);

  const windows = useMemo(() => {
    const routeWindows = byRoute[DESKTOP_ROUTE] ?? {};
    return Object.values(routeWindows).sort((a, b) => a.zIndex - b.zIndex);
  }, [byRoute]);

  const taskbarReserve = useMemo(
    () => (windows.some((w) => w.mode === "minimized") ? 30 : 0),
    [windows]
  );

  useEffect(() => {
    if (!focusedWindowId) return;
    const win = windows.find((w) => w.id === focusedWindowId);
    if (!win || win.mode === "closed" || win.mode === "minimized") {
      setFocusedWindowId(pickTopFocusableWindow(windows));
    }
  }, [windows, focusedWindowId]);

  const mutateDesktop = useCallback((fn: (current: RouteWindows) => RouteWindows) => {
    setByRoute((prev) => ({
      ...prev,
      [DESKTOP_ROUTE]: fn(prev[DESKTOP_ROUTE] ?? {}),
    }));
  }, []);

  const markNavForWindow = useCallback((windowId: string) => {
    if (windowId.startsWith("template-")) {
      setActiveNavSection("social");
      return;
    }
    const section = WINDOW_NAV_SECTION[windowId];
    if (section) setActiveNavSection(section);
  }, []);

  const registerWindow = useCallback(
    (reg: WindowRegistration) => {
      const focusPending = peekPendingNotificationFocus() === reg.id;
      mutateDesktop((current) => {
        const existing = current[reg.id];
        if (existing) {
          if (focusPending && consumePendingNotificationFocus(reg.id)) {
            zCounterRef.current += 1;
            return {
              ...current,
              [reg.id]: {
                ...existing,
                title: reg.title,
                mode: existing.mode === "minimized" ? "open" : existing.mode,
                zIndex: zCounterRef.current,
              },
            };
          }
          return {
            ...current,
            [reg.id]: { ...existing, title: reg.title },
          };
        }
        const index = registerCounterRef.current;
        registerCounterRef.current += 1;
        const fallback = staggerPosition(index);
        zCounterRef.current += 1;
        const nextWin: WindowState = {
          id: reg.id,
          title: reg.title,
          mode: focusPending ? "open" : "closed",
          x: reg.defaultX ?? fallback.x,
          y: reg.defaultY ?? fallback.y,
          width: reg.defaultWidth ?? 360,
          height: reg.defaultHeight ?? null,
          zIndex: zCounterRef.current,
        };
        if (focusPending) consumePendingNotificationFocus(reg.id);
        return {
          ...current,
          [reg.id]: nextWin,
        };
      });
    },
    [mutateDesktop]
  );

  const unregisterWindow = useCallback((_id: string) => {
    /* Keep layout in byRoute so position/size survive route changes and refresh. */
  }, []);

  const setMode = useCallback(
    (id: string, mode: WindowMode) => {
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;
        return { ...current, [id]: { ...win, mode } };
      });
    },
    [mutateDesktop]
  );

  const minimizeWindow = useCallback(
    (id: string) => {
      mutateDesktop((current) => {
        const win = current[id];
        if (!win || win.mode === "minimized" || win.mode === "closed") return current;

        const restoreX = win.mode === "maximized" ? (win.restoreX ?? win.x) : win.x;
        const restoreY = win.mode === "maximized" ? (win.restoreY ?? win.y) : win.y;
        const restoreWidth = win.mode === "maximized" ? (win.restoreWidth ?? win.width) : win.width;
        const restoreHeight =
          win.mode === "maximized" ? (win.restoreHeight ?? win.height) : win.height;

        return {
          ...current,
          [id]: {
            ...win,
            mode: "minimized",
            restoreX,
            restoreY,
            restoreWidth,
            restoreHeight,
          },
        };
      });
    },
    [mutateDesktop]
  );

  const maximizeWindow = useCallback(
    (id: string) => {
      zCounterRef.current += 1;
      mutateDesktop((current) => {
        const win = current[id];
        if (!win || win.mode === "closed") return current;
        return {
          ...current,
          [id]: {
            ...win,
            mode: "maximized",
            restoreX: win.restoreX ?? win.x,
            restoreY: win.restoreY ?? win.y,
            restoreWidth: win.restoreWidth ?? win.width,
            restoreHeight: win.restoreHeight ?? win.height,
            zIndex: zCounterRef.current,
          },
        };
      });
    },
    [mutateDesktop]
  );

  const restoreWindow = useCallback(
    (id: string) => {
      zCounterRef.current += 1;
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;
        const hasRestore = win.restoreWidth !== undefined && win.restoreX !== undefined;
        return {
          ...current,
          [id]: {
            ...win,
            mode: "open",
            zIndex: zCounterRef.current,
            ...(hasRestore
              ? {
                  x: win.restoreX!,
                  y: win.restoreY ?? win.y,
                  width: win.restoreWidth!,
                  height: win.restoreHeight ?? win.height,
                }
              : {}),
          },
        };
      });
    },
    [mutateDesktop]
  );

  const setPosition = useCallback(
    (id: string, x: number, y: number) => {
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;
        return { ...current, [id]: { ...win, x, y } };
      });
    },
    [mutateDesktop]
  );

  const setBounds = useCallback(
    (id: string, x: number, y: number, width: number, height: number) => {
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;
        return {
          ...current,
          [id]: {
            ...win,
            x,
            y,
            width,
            height,
            restoreX: x,
            restoreY: y,
            restoreWidth: width,
            restoreHeight: height,
          },
        };
      });
    },
    [mutateDesktop]
  );

  const focusWindow = useCallback(
    (id: string) => {
      zCounterRef.current += 1;
      setFocusedWindowId(id);
      markNavForWindow(id);
      setNeocomPanelOpen(true);
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;
        return { ...current, [id]: { ...win, zIndex: zCounterRef.current } };
      });
    },
    [mutateDesktop, markNavForWindow]
  );

  const openWindow = useCallback(
    (id: string) => {
      zCounterRef.current += 1;
      mutateDesktop((current) => {
        const win = current[id];
        if (!win) return current;

        const hasRestore =
          win.restoreX !== undefined &&
          win.restoreY !== undefined &&
          win.restoreWidth !== undefined;

        return {
          ...current,
          [id]: {
            ...win,
            mode: "open",
            zIndex: zCounterRef.current,
            ...(hasRestore
              ? {
                  x: win.restoreX!,
                  y: win.restoreY!,
                  width: win.restoreWidth!,
                  height: win.restoreHeight ?? win.height,
                }
              : {}),
          },
        };
      });
    },
    [mutateDesktop]
  );

  const openNavSection = useCallback((navSectionId: string) => {
    setActiveNavSection(navSectionId);
    setNeocomPanelOpen(true);
    syncDesktopUrl({ tool: null });
  }, []);

  const selectNavSection = useCallback(
    (navSectionId: string) => {
      setActiveNavSection((prev) => {
        if (prev === navSectionId) {
          setNeocomPanelOpen((open) => !open);
          return prev;
        }
        setNeocomPanelOpen(true);
        return navSectionId;
      });
      syncDesktopUrl({ tool: null });
    },
    []
  );

  const toggleWindowFromNeocom = useCallback(
    (windowId: string, slug?: string) => {
      const win = windows.find((w) => w.id === windowId);
      if (!win || win.mode === "closed") {
        if (slug) {
          openToolInDesktop(slug, windowId, openWindow, focusWindow);
          return;
        }
        openWindow(windowId);
        focusWindow(windowId);
        syncDesktopUrl({ tool: null });
        return;
      }
      if (win.mode === "minimized") {
        openWindow(windowId);
        focusWindow(windowId);
        return;
      }
      if (focusedWindowId === windowId && win.mode === "open") {
        minimizeWindow(windowId);
        return;
      }
      focusWindow(windowId);
    },
    [windows, focusedWindowId, openWindow, focusWindow, minimizeWindow]
  );

  const launchSection = useCallback(
    (navSectionId: string, windowId?: string) => {
      setActiveNavSection(navSectionId);
      setNeocomPanelOpen(true);
      syncDesktopUrl({ tool: null });
      let targetId: string | undefined = windowId ?? NAV_LAUNCH_WINDOWS[navSectionId];
      const section = getNavSection(navSectionId);
      if (!targetId && section?.includeTemplateWindows) {
        targetId = windows.find((w) => w.id.startsWith("template-"))?.id;
      }
      if (!targetId) return;
      openWindow(targetId);
      focusWindow(targetId);
    },
    [windows, openWindow, focusWindow]
  );

  const toggleNeocomPanel = useCallback(() => {
    setNeocomPanelOpen((open) => !open);
  }, []);

  const closeAllWindows = useCallback(() => {
    mutateDesktop((current) => {
      const next: RouteWindows = { ...current };
      for (const [id, win] of Object.entries(next)) {
        next[id] = { ...win, mode: "closed" };
      }
      return next;
    });
    setFocusedWindowId(null);
    syncDesktopUrl({ tool: null });
  }, [mutateDesktop]);

  const value = useMemo(
    () => ({
      route: DESKTOP_ROUTE,
      windows,
      activeNavSection,
      neocomPanelOpen,
      focusedWindowId,
      taskbarReserve,
      registerWindow,
      unregisterWindow,
      setMode,
      setPosition,
      setBounds,
      focusWindow,
      openWindow,
      launchSection,
      selectNavSection,
      openNavSection,
      toggleWindowFromNeocom,
      toggleNeocomPanel,
      setNeocomPanelOpen,
      minimizeWindow,
      maximizeWindow,
      restoreWindow,
      closeAllWindows,
      desktopRef,
    }),
    [
      windows,
      activeNavSection,
      neocomPanelOpen,
      focusedWindowId,
      taskbarReserve,
      registerWindow,
      unregisterWindow,
      setMode,
      setPosition,
      setBounds,
      focusWindow,
      openWindow,
      launchSection,
      selectNavSection,
      openNavSection,
      toggleWindowFromNeocom,
      toggleNeocomPanel,
      minimizeWindow,
      maximizeWindow,
      restoreWindow,
      closeAllWindows,
    ]
  );

  return (
    <WindowManagerContext.Provider value={value}>{children}</WindowManagerContext.Provider>
  );
}

export function useWindowManager() {
  const ctx = useContext(WindowManagerContext);
  if (!ctx) {
    throw new Error("useWindowManager must be used within WindowManagerProvider");
  }
  return ctx;
}

export function useWindowManagerOptional() {
  return useContext(WindowManagerContext);
}

function ToolQueryFocus() {
  const searchParams = useSearchParams();
  const { windows, openWindow, focusWindow } = useWindowManager();
  const appliedToolRef = useRef<string | null>(null);
  const pendingToolRef = useRef<string | null>(null);

  const toolFromUrl = searchParams.get("tool");
  if (toolFromUrl) pendingToolRef.current = toolFromUrl;

  const tool = pendingToolRef.current;
  const windowId = tool ? resolveToolWindowId(tool) : null;
  const winExists = windowId ? windows.some((w) => w.id === windowId) : false;

  useEffect(() => {
    if (!tool || !windowId) {
      appliedToolRef.current = null;
      return;
    }
    if (!winExists) return;
    if (appliedToolRef.current === tool) return;
    appliedToolRef.current = tool;
    openWindow(windowId);
    focusWindow(windowId);
    syncDesktopUrl({ tool });
  }, [tool, windowId, winExists, openWindow, focusWindow]);

  return null;
}

function StartupAboutWindow() {
  const searchParams = useSearchParams();
  const { windows, openWindow, focusWindow, openNavSection } = useWindowManager();
  const openedRef = useRef(false);

  useEffect(() => {
    if (searchParams.get("tool")) return;
    if (openedRef.current) return;
    if (!windows.some((w) => w.id === "about")) return;
    openedRef.current = true;
    openWindow("about");
    focusWindow("about");
    openNavSection("utilities");
  }, [searchParams, windows, openWindow, focusWindow, openNavSection]);

  return null;
}

export function DesktopSurface({
  embedded,
  children,
  className,
}: {
  embedded?: boolean;
  children: ReactNode;
  className?: string;
}) {
  if (embedded) return <>{children}</>;
  return <WindowDesktop className={className ?? "min-h-0 flex-1"}>{children}</WindowDesktop>;
}

export function WindowDesktop({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { desktopRef, windows, openWindow, focusWindow } = useWindowManager();
  const minimized = windows.filter((w) => w.mode === "minimized");

  return (
    <div
      ref={desktopRef}
      className={clsx("eve-window-desktop", className, minimized.length > 0 && "eve-window-desktop--has-taskbar")}
      style={{ ["--window-taskbar-h" as string]: minimized.length > 0 ? "30px" : "0px" }}
    >
      <Suspense fallback={null}>
        <ToolQueryFocus />
        <StartupAboutWindow />
      </Suspense>
      {minimized.length > 0 ? (
        <div className="eve-window-taskbar" role="toolbar" aria-label="Minimized windows">
          {minimized.map((win) => (
            <button
              key={win.id}
              type="button"
              className="eve-window-taskbar-btn"
              title={`Restore ${win.title}`}
              onClick={() => {
                openWindow(win.id);
                focusWindow(win.id);
              }}
            >
              <WindowTaskbarIcon windowId={win.id} className="eve-window-taskbar-icon" />
              <span className="eve-window-taskbar-label">{win.title}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="eve-window-desktop-surface">{children}</div>
    </div>
  );
}
