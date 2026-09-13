"use client";

import { getNotificationMeta } from "@/lib/notifications/types";
import { NotificationIcon } from "./NotificationBell";
import { useNotifications } from "./NotificationProvider";

export function NotificationToasts() {
  const { toasts, dismissToast, navigateToNotification } = useNotifications();

  if (toasts.length === 0) return null;

  return (
    <div className="eve-notify-toasts" aria-live="polite">
      {toasts.map((n) => {
        const meta = getNotificationMeta(n.plugin, n.type);
        return (
          <div key={n.id} className="eve-notify-toast">
            <button
              type="button"
              className="eve-notify-toast-main"
              onClick={() => void navigateToNotification(n)}
            >
              <span className="eve-notify-toast-icon">
                <NotificationIcon plugin={n.plugin} type={n.type} />
              </span>
              <span className="eve-notify-toast-body">
                <span className="eve-notify-toast-kicker">{meta.label}</span>
                <span className="eve-notify-toast-title">{n.title}</span>
                <span className="eve-notify-toast-msg">{n.body}</span>
              </span>
            </button>
            <button
              type="button"
              className="eve-notify-toast-close"
              aria-label="Dismiss"
              onClick={(e) => {
                e.stopPropagation();
                dismissToast(n.id);
              }}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
