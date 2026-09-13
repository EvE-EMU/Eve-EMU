"use client";

import clsx from "clsx";
import { getNotificationMeta } from "@/lib/notifications/types";
import { NotificationIcon } from "./NotificationBell";
import { useNotifications } from "./NotificationProvider";

function formatWhen(iso: string) {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "Just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString();
}

export function NotificationPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notifications, unreadCount, markAllRead, navigateToNotification } = useNotifications();

  if (!open) return null;

  return (
    <div className="eve-notify-panel" role="dialog" aria-label="Notifications">
      <header className="eve-notify-panel-head">
        <div>
          <p className="eve-notify-panel-kicker">Notifications</p>
          <p className="eve-notify-panel-sub">
            {unreadCount > 0 ? `${unreadCount} unread` : "All caught up"}
          </p>
        </div>
        <div className="flex gap-1">
          {unreadCount > 0 ? (
            <button type="button" className="eve-btn-sm" onClick={() => void markAllRead()}>
              Mark all read
            </button>
          ) : null}
          <button type="button" className="eve-wc-btn eve-wc-close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
      </header>
      <ul className="eve-notify-list eve-scroll">
        {notifications.length === 0 ? (
          <li className="eve-notify-empty">No notifications.</li>
        ) : (
          notifications.map((n) => {
            const meta = getNotificationMeta(n.plugin, n.type);
            return (
              <li key={n.id}>
                <button
                  type="button"
                  className={clsx("eve-notify-item", !n.read && "eve-notify-item--unread")}
                  onClick={() => void navigateToNotification(n)}
                >
                  <span className="eve-notify-item-icon">
                    <NotificationIcon plugin={n.plugin} type={n.type} />
                  </span>
                  <span className="eve-notify-item-body">
                    <span className="eve-notify-item-title">{n.title}</span>
                    <span className="eve-notify-item-msg">{n.body}</span>
                    <span className="eve-notify-item-meta">
                      {meta.label} · {formatWhen(n.created_at)}
                    </span>
                  </span>
                  {!n.read ? <span className="eve-notify-item-dot" aria-hidden /> : null}
                </button>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}
