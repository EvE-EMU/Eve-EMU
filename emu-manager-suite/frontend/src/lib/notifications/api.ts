import type { NotificationRecord } from "./types";

export async function fetchNotifications(opts?: {
  unreadOnly?: boolean;
  sinceId?: number;
}): Promise<NotificationRecord[]> {
  const params = new URLSearchParams();
  if (opts?.unreadOnly) params.set("unread_only", "true");
  if (opts?.sinceId) params.set("since_id", String(opts.sinceId));
  const q = params.toString();
  const res = await fetch(`/api/notifications${q ? `?${q}` : ""}`, {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("Failed to load notifications");
  return res.json() as Promise<NotificationRecord[]>;
}

export async function fetchUnreadCount(): Promise<number> {
  const res = await fetch("/api/notifications/unread-count", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!res.ok) return 0;
  const data = (await res.json()) as { count: number };
  return data.count;
}

export async function markNotificationsRead(ids: number[]): Promise<void> {
  await fetch("/api/notifications/read", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
}

export async function markAllNotificationsRead(): Promise<void> {
  await fetch("/api/notifications/read", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ all: true }),
  });
}
