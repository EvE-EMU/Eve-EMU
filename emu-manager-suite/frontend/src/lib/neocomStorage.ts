const STORAGE_KEY = "emums-neocom-prefs-v1";

export type NeocomPrefs = {
  panelOpen: boolean;
  activeSection: string;
};

const DEFAULT_PREFS: NeocomPrefs = {
  panelOpen: true,
  activeSection: "personal",
};

export function loadNeocomPrefs(): NeocomPrefs {
  if (typeof window === "undefined") return DEFAULT_PREFS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw) as Partial<NeocomPrefs>;
    return {
      panelOpen: typeof parsed.panelOpen === "boolean" ? parsed.panelOpen : DEFAULT_PREFS.panelOpen,
      activeSection:
        typeof parsed.activeSection === "string" && parsed.activeSection.length > 0
          ? parsed.activeSection
          : DEFAULT_PREFS.activeSection,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function saveNeocomPrefs(prefs: NeocomPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota errors */
  }
}
