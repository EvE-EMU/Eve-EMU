import type { NotificationRecord } from "./types";

export type NotificationTarget = {
  href: string;
  windowId?: string;
};

type TargetResolver = (notification: NotificationRecord) => NotificationTarget | null;

const TARGET_RESOLVERS: TargetResolver[] = [];

/** Addons register how their notifications map to app routes/windows. */
export function registerNotificationTargetResolver(resolver: TargetResolver) {
  TARGET_RESOLVERS.push(resolver);
}

const MOONS_WINDOWS: Record<string, string> = {
  tax_bill: "moon-tax",
  extraction_ready: "moon-productivity",
};

registerNotificationTargetResolver((n) => {
  if (n.plugin === "moons") {
    return {
      href: "/",
      windowId: MOONS_WINDOWS[n.type] ?? "observer-log",
    };
  }
  if (n.plugin === "system") {
    return { href: "/" };
  }
  return null;
});

export function resolveNotificationTarget(notification: NotificationRecord): NotificationTarget {
  for (const resolver of TARGET_RESOLVERS) {
    const target = resolver(notification);
    if (target) return target;
  }
  return { href: "/" };
}

let pendingWindowFocus: string | null = null;

export function setPendingNotificationFocus(windowId: string | null) {
  pendingWindowFocus = windowId;
}

export function consumePendingNotificationFocus(windowId: string): boolean {
  if (pendingWindowFocus !== windowId) return false;
  pendingWindowFocus = null;
  return true;
}

export function peekPendingNotificationFocus(): string | null {
  return pendingWindowFocus;
}
