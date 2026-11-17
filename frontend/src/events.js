export const NOTIFICATIONS_CHANGED = "stockpilot:notifications-changed";

export const announceNotificationsChanged = () =>
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
