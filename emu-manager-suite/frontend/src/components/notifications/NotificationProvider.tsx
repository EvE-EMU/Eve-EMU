"use client";

import "@/lib/notifications/types";
import "@/lib/notifications/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationsRead,
} from "@/lib/notifications/api";
import {
  resolveNotificationTarget,
  setPendingNotificationFocus,
} from "@/lib/notifications/navigation";
import type { NotificationRecord } from "@/lib/notifications/types";
import { useAuth } from "@/components/AuthProvider";

const POLL_MS = 20_000;
const TOAST_MS = 5_500;

type NotificationContextValue = {
  notifications: NotificationRecord[];
  unreadCount: number;
  panelOpen: boolean;
  toasts: NotificationRecord[];
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
  markRead: (ids: number[]) => Promise<void>;
  markAllRead: () => Promise<void>;
  dismissToast: (id: number) => void;
  refresh: () => Promise<void>;
  navigateToNotification: (notification: NotificationRecord) => Promise<void>;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { session } = useAuth();
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [panelOpen, setPanelOpen] = useState(false);
  const [toasts, setToasts] = useState<NotificationRecord[]>([]);
  const knownIdsRef = useRef<Set<number>>(new Set());
  const initializedRef = useRef(false);

  const pushToasts = useCallback((items: NotificationRecord[]) => {
    if (items.length === 0) return;
    setToasts((prev) => {
      const existing = new Set(prev.map((t) => t.id));
      const next = [...prev];
      for (const item of items) {
        if (!existing.has(item.id)) next.push(item);
      }
      return next.slice(-4);
    });
    for (const item of items) {
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== item.id));
      }, TOAST_MS);
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!session.authenticated) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    try {
      const [rows, count] = await Promise.all([fetchNotifications(), fetchUnreadCount()]);
      setNotifications(rows);
      setUnreadCount(count);

      if (!initializedRef.current) {
        for (const row of rows) knownIdsRef.current.add(row.id);
        initializedRef.current = true;
        return;
      }

      const fresh = rows.filter((r) => !r.read && !knownIdsRef.current.has(r.id));
      for (const row of rows) knownIdsRef.current.add(row.id);
      if (fresh.length > 0) pushToasts(fresh);
    } catch {
      /* API unavailable — silent */
    }
  }, [pushToasts, session.authenticated]);

  useEffect(() => {
    if (!session.authenticated) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh, session.authenticated]);

  const markRead = useCallback(async (ids: number[]) => {
    await markNotificationsRead(ids);
    setNotifications((prev) =>
      prev.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n))
    );
    setUnreadCount((c) => Math.max(0, c - ids.length));
  }, []);

  const markAllRead = useCallback(async () => {
    await markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const navigateToNotification = useCallback(
    async (notification: NotificationRecord) => {
      const target = resolveNotificationTarget(notification);
      if (target.windowId) setPendingNotificationFocus(target.windowId);
      if (!notification.read) await markRead([notification.id]);
      setPanelOpen(false);
      dismissToast(notification.id);
      router.push(target.href);
    },
    [markRead, dismissToast, router]
  );

  const value = useMemo(
    () => ({
      notifications,
      unreadCount,
      panelOpen,
      toasts,
      openPanel: () => setPanelOpen(true),
      closePanel: () => setPanelOpen(false),
      togglePanel: () => setPanelOpen((v) => !v),
      markRead,
      markAllRead,
      dismissToast,
      refresh,
      navigateToNotification,
    }),
    [
      notifications,
      unreadCount,
      panelOpen,
      toasts,
      markRead,
      markAllRead,
      dismissToast,
      refresh,
      navigateToNotification,
    ]
  );

  return (
    <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
  return ctx;
}
