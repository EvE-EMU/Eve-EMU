"use client";

import clsx from "clsx";
import { getNotificationMeta } from "@/lib/notifications/types";
import { useNotifications } from "./NotificationProvider";
import { NotificationPanel } from "./NotificationPanel";
import { NotificationToasts } from "./NotificationToasts";
import { Tooltip } from "../Tooltip";

function IconBell({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M8 1.8a3.2 3.2 0 0 1 3.2 3.2c0 2.8.9 3.6 1.6 4.4v.8H3.2v-.8c.7-.8 1.6-1.6 1.6-4.4A3.2 3.2 0 0 1 8 1.8z" />
      <path d="M6.2 13.2h3.6M8 13.2v1" />
    </svg>
  );
}

function NotificationIcon({ plugin, type }: { plugin: string; type: string }) {
  const meta = getNotificationMeta(plugin, type);
  const cls = "eve-notify-type-icon";
  if (meta.icon === "moon") {
    return (
      <svg className={cls} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
        <circle cx="8" cy="8" r="5" />
        <path d="M11 4.5a4 4 0 1 0 0 7" />
      </svg>
    );
  }
  if (meta.icon === "tax" || meta.icon === "rental") {
    return (
      <svg className={cls} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
        <rect x="3" y="2.5" width="10" height="11" />
        <path d="M5.5 6h5M5.5 8.5h5M5.5 11h3" />
      </svg>
    );
  }
  return (
    <svg className={cls} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 5v3.5l2 1.2" />
    </svg>
  );
}

export function NotificationBell() {
  const { unreadCount, panelOpen, togglePanel, closePanel } = useNotifications();

  return (
    <>
      <div className="eve-notify-anchor">
        <Tooltip label="Notifications" side="top">
          <button
            type="button"
            className={clsx("eve-notify-bell", panelOpen && "eve-notify-bell--open")}
            aria-label={`Notifications${unreadCount ? ` — ${unreadCount} unread` : ""}`}
            onClick={togglePanel}
          >
            <IconBell className="eve-notify-bell-icon" />
            {unreadCount > 0 ? (
              <span className="eve-notify-badge" aria-hidden>
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            ) : null}
          </button>
        </Tooltip>
        <NotificationPanel open={panelOpen} onClose={closePanel} />
      </div>
      <NotificationToasts />
    </>
  );
}

export { NotificationIcon };
