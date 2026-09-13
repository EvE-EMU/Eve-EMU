const STORAGE_KEY = "emums-window-layout-v2";

import { DESKTOP_ROUTE } from "./desktop";

export type WindowMode = "open" | "minimized" | "maximized" | "closed";

export type StoredWindowState = {
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

export type PersistedWindowLayout = Record<string, Record<string, StoredWindowState>>;

export { DESKTOP_ROUTE };

const VALID_MODES: WindowMode[] = ["open", "minimized", "maximized", "closed"];

function isValidWindowState(raw: unknown): raw is StoredWindowState {
  if (!raw || typeof raw !== "object") return false;
  const w = raw as StoredWindowState;
  const heightOk =
    w.height === null ||
    (typeof w.height === "number" && Number.isFinite(w.height) && w.height >= 22);
  const restoreHeightOk =
    w.restoreHeight === undefined ||
    w.restoreHeight === null ||
    (typeof w.restoreHeight === "number" && Number.isFinite(w.restoreHeight) && w.restoreHeight >= 72);
  return (
    typeof w.id === "string" &&
    typeof w.title === "string" &&
    VALID_MODES.includes(w.mode) &&
    typeof w.x === "number" &&
    Number.isFinite(w.x) &&
    typeof w.y === "number" &&
    Number.isFinite(w.y) &&
    typeof w.width === "number" &&
    Number.isFinite(w.width) &&
    w.width >= 160 &&
    heightOk &&
    typeof w.zIndex === "number" &&
    Number.isFinite(w.zIndex) &&
    restoreHeightOk
  );
}

/** Merge per-route saved layouts into one global desktop bucket. */
export function migrateToGlobalDesktop(layout: PersistedWindowLayout): PersistedWindowLayout {
  if (layout[DESKTOP_ROUTE] && Object.keys(layout[DESKTOP_ROUTE]).length > 0) {
    return layout;
  }
  const merged: Record<string, StoredWindowState> = { ...(layout[DESKTOP_ROUTE] ?? {}) };
  for (const [route, windows] of Object.entries(layout)) {
    if (route === DESKTOP_ROUTE || !windows) continue;
    for (const [id, state] of Object.entries(windows)) {
      const existing = merged[id];
      if (!existing || state.zIndex >= existing.zIndex) {
        merged[id] = state;
      }
    }
  }
  return { [DESKTOP_ROUTE]: merged };
}

export function loadWindowLayout(): PersistedWindowLayout {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const legacy = window.localStorage.getItem("emums-window-layout-v1");
      if (legacy) {
        const parsed = JSON.parse(legacy) as PersistedWindowLayout;
        window.localStorage.setItem(STORAGE_KEY, legacy);
        return migrateToGlobalDesktop(layoutWithClosedModes(sanitizeLayout(parsed)));
      }
      return {};
    }
    return migrateToGlobalDesktop(layoutWithClosedModes(sanitizeLayout(JSON.parse(raw) as PersistedWindowLayout)));
  } catch {
    return {};
  }
}

function sanitizeLayout(parsed: PersistedWindowLayout): PersistedWindowLayout {
  if (!parsed || typeof parsed !== "object") return {};
  const out: PersistedWindowLayout = {};
  for (const [route, windows] of Object.entries(parsed)) {
    if (!windows || typeof windows !== "object") continue;
    const cleaned: Record<string, StoredWindowState> = {};
    for (const [id, state] of Object.entries(windows)) {
      if (isValidWindowState(state)) cleaned[id] = state;
    }
    if (Object.keys(cleaned).length > 0) out[route] = cleaned;
  }
  return out;
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

export function saveWindowLayout(layout: PersistedWindowLayout) {
  if (typeof window === "undefined") return;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    } catch {
      /* quota / private mode */
    }
    saveTimer = null;
  }, 200);
}

export function maxZIndex(layout: PersistedWindowLayout): number {
  let max = 10;
  for (const routeWindows of Object.values(layout)) {
    for (const win of Object.values(routeWindows)) {
      if (win.zIndex > max) max = win.zIndex;
    }
  }
  return max;
}

/** Window geometry persists; open/minimized state is session-only. */
export function layoutWithClosedModes(layout: PersistedWindowLayout): PersistedWindowLayout {
  const out: PersistedWindowLayout = {};
  for (const [route, windows] of Object.entries(layout)) {
    if (!windows) continue;
    const closed: Record<string, StoredWindowState> = {};
    for (const [id, win] of Object.entries(windows)) {
      closed[id] = { ...win, mode: "closed" };
    }
    if (Object.keys(closed).length > 0) out[route] = closed;
  }
  return out;
}
