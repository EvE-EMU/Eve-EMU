export type DesktopBackground = {
  id: number;
  label: string;
  video_url: string;
  active: boolean;
  sort_order: number;
  created_at: string;
};

export type DesktopBackgroundInput = {
  label: string;
  video_url: string;
  active?: boolean;
  sort_order?: number;
};

export async function fetchActiveDesktopBackgrounds(): Promise<DesktopBackground[]> {
  const res = await fetch("/api/desktop-backgrounds", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load desktop backgrounds");
  return res.json() as Promise<DesktopBackground[]>;
}

export async function fetchAllDesktopBackgrounds(): Promise<DesktopBackground[]> {
  const res = await fetch("/api/desktop-backgrounds?all=1", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load desktop backgrounds");
  return res.json() as Promise<DesktopBackground[]>;
}

export async function createDesktopBackground(
  payload: DesktopBackgroundInput
): Promise<DesktopBackground> {
  const res = await fetch("/api/desktop-backgrounds", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create background");
  return res.json() as Promise<DesktopBackground>;
}

export async function updateDesktopBackground(
  id: number,
  payload: Partial<DesktopBackgroundInput>
): Promise<DesktopBackground> {
  const res = await fetch(`/api/desktop-backgrounds/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update background");
  return res.json() as Promise<DesktopBackground>;
}

export async function deleteDesktopBackground(id: number): Promise<void> {
  const res = await fetch(`/api/desktop-backgrounds/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete background");
}

export async function uploadDesktopBackground(
  file: File,
  label: string
): Promise<DesktopBackground> {
  const form = new FormData();
  form.append("file", file);
  form.append("label", label.trim());
  const res = await fetch("/api/desktop-backgrounds/upload", {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = "Failed to upload video";
    try {
      const data = (await res.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<DesktopBackground>;
}

export function pickRandomBackground(
  backgrounds: DesktopBackground[]
): DesktopBackground | null {
  if (backgrounds.length === 0) return null;
  return backgrounds[Math.floor(Math.random() * backgrounds.length)];
}
