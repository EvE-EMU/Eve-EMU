/** Local display preferences — font and UI scale (persisted per browser). */

export type FontId = "system" | "verdana" | "arial" | "tahoma" | "georgia";

export type DisplayPrefs = {
  fontId: FontId;
  uiScale: number;
};

export const UI_SCALE_REFERENCE = 1.15;
export const UI_SCALE_MIN = 0.9;
export const UI_SCALE_MAX = 1.85;
export const UI_SCALE_STEP = 0.05;

export const FONT_OPTIONS: { id: FontId; label: string; stack: string }[] = [
  {
    id: "system",
    label: "Default (Segoe UI)",
    stack: '"Segoe UI", Tahoma, "Helvetica Neue", Arial, sans-serif',
  },
  {
    id: "verdana",
    label: "Verdana — easy reading",
    stack: "Verdana, Geneva, Tahoma, sans-serif",
  },
  {
    id: "arial",
    label: "Arial",
    stack: 'Arial, "Helvetica Neue", Helvetica, sans-serif',
  },
  {
    id: "tahoma",
    label: "Tahoma — clear labels",
    stack: "Tahoma, Verdana, Segoe UI, sans-serif",
  },
  {
    id: "georgia",
    label: "Georgia — serif",
    stack: 'Georgia, "Times New Roman", Times, serif',
  },
];

export const UI_SCALE_PRESETS: { id: string; label: string; value: number }[] = [
  { id: "compact", label: "Compact", value: 1.0 },
  { id: "default", label: "Default", value: UI_SCALE_REFERENCE },
  { id: "large", label: "Large", value: 1.3 },
  { id: "xlarge", label: "Extra large", value: 1.5 },
  { id: "xxlarge", label: "Maximum", value: 1.7 },
];

const STORAGE_KEY = "emums-display-prefs-v1";

export const DEFAULT_DISPLAY_PREFS: DisplayPrefs = {
  fontId: "system",
  uiScale: UI_SCALE_REFERENCE,
};

const FONT_IDS = new Set(FONT_OPTIONS.map((f) => f.id));

export function clampUiScale(value: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return UI_SCALE_REFERENCE;
  return Math.min(UI_SCALE_MAX, Math.max(UI_SCALE_MIN, Math.round(n * 100) / 100));
}

export function fontStack(fontId: FontId): string {
  return FONT_OPTIONS.find((f) => f.id === fontId)?.stack ?? FONT_OPTIONS[0].stack;
}

export function loadDisplayPrefs(): DisplayPrefs {
  if (typeof window === "undefined") return DEFAULT_DISPLAY_PREFS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_DISPLAY_PREFS;
    const parsed = JSON.parse(raw) as Partial<DisplayPrefs>;
    const fontId = FONT_IDS.has(parsed.fontId as FontId)
      ? (parsed.fontId as FontId)
      : DEFAULT_DISPLAY_PREFS.fontId;
    return {
      fontId,
      uiScale: clampUiScale(parsed.uiScale ?? DEFAULT_DISPLAY_PREFS.uiScale),
    };
  } catch {
    return DEFAULT_DISPLAY_PREFS;
  }
}

export function saveDisplayPrefs(prefs: DisplayPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota errors */
  }
}

export function applyDisplayPrefs(prefs: DisplayPrefs): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const scale = clampUiScale(prefs.uiScale);
  root.style.setProperty("--ui-scale", String(scale));
  root.style.setProperty("--app-font", fontStack(prefs.fontId));
  root.style.setProperty("--ui-zoom", String(scale));
  root.dataset.fontId = prefs.fontId;
  root.dataset.uiScale = String(scale);
}

/** Inline boot script — keeps first paint close to saved prefs. */
export function displayPrefsBootScript(): string {
  const fontMap = Object.fromEntries(FONT_OPTIONS.map((f) => [f.id, f.stack]));
  return `(function(){try{var k="emums-display-prefs-v1",r=document.documentElement,p=JSON.parse(localStorage.getItem(k)||"{}"),ref=${UI_SCALE_REFERENCE},fonts=${JSON.stringify(fontMap)},scale=Math.min(${UI_SCALE_MAX},Math.max(${UI_SCALE_MIN},Number(p.uiScale)||ref));r.style.setProperty("--ui-scale",String(scale));r.style.setProperty("--ui-zoom",String(scale));if(p.fontId&&fonts[p.fontId])r.style.setProperty("--app-font",fonts[p.fontId]);}catch(e){}})();`;
}
