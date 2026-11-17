import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { EmptyState } from "../../components/ui";
import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import { announceNotificationsChanged as announce } from "../../events";
import { dateTime, timeAgo } from "../../format";
import { notifications } from "../../store";

// A picture for each kind of message.
function iconFor(message) {
  if (/stock/i.test(message)) return "box";
  if (/repair/i.test(message)) return "wrench";
  if (/PO-|order/i.test(message)) return "truck";
  if (/request/i.test(message)) return "inbox";
  if (/role/i.test(message)) return "user";
  return "bell";
}

export default function NotificationsPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.notifications);
  const [unreadOnly, setUnreadOnly] = useState(true);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    dispatch(notifications.fetchList({ unread: unreadOnly ? "true" : "", page, per_page: 15 }));
  }, [dispatch, unreadOnly, page]);

  const optimistic = async (change, request) => {
    const before = { items: list.items, count: list.count };
    change();
    setError("");
    try {
      await request();
      announce();
    } catch (err) {
      dispatch(notifications.actions.restoreItems(before));
      setError(err.message);
    }
  };

  const markRead = (note) =>
    optimistic(
      () => dispatch(notifications.actions.patchItem({ id: note.id, changes: { is_read: true } })),
      () => api(`/api/notifications/${note.id}/read`, { method: "POST" }),
    );

  const markAll = () =>
    optimistic(
      () =>
        list.items.forEach((note) =>
          dispatch(notifications.actions.patchItem({ id: note.id, changes: { is_read: true } })),
        ),
      () => api("/api/notifications/read-all", { method: "POST" }),
    );

  const unreadHere = list.items.filter((note) => !note.is_read).length;

  return (
    <section className="flex max-w-4xl flex-col gap-6">
      <PageHeader title="Notifications" subtitle="Updates about your own work.">
        <button type="button" onClick={markAll} disabled={!unreadHere} className="btn-secondary">
          Mark all as read
        </button>
      </PageHeader>

      {(error || list.error) && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      <div className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <div role="group" aria-label="Show" className="seg">
            {[
              [true, "Unread"],
              [false, "All"],
            ].map(([value, text]) => (
              <button
                key={text}
                type="button"
                aria-pressed={unreadOnly === value}
                onClick={() => {
                  setUnreadOnly(value);
                  setPage(1);
                }}
              >
                {text}
              </button>
            ))}
          </div>
          {list.status === "ready" && (
            <span className="text-sm text-muted">{unreadHere} unread on this page</span>
          )}
        </div>
        {list.status === "loading" && list.items.length === 0 && (
          <div className="p-5">
            <SkeletonCards count={3} />
          </div>
        )}
        {list.status === "ready" && list.items.length === 0 && (
          <EmptyState
            icon="bell"
            title={unreadOnly ? "You are all caught up." : "No notifications yet."}
          >
            Low stock, decisions on your requests, deliveries and repairs show up here.
          </EmptyState>
        )}

        <ul className="divide-y divide-line">
          {list.items.map((note) => (
            <li
              key={note.id}
              className={`flex items-start gap-4 px-5 py-4 transition-colors ${note.is_read ? "" : "bg-saffron-soft/40"}`}
            >
              <span
                className={`grid size-10 shrink-0 place-items-center rounded-xl ${note.is_read ? "bg-surface-2 text-muted" : "bg-surface text-saffron-ink ring-1 ring-saffron/40"}`}
              >
                <Icon name={iconFor(note.message)} size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block text-sm ${note.is_read ? "text-ink-2" : "font-semibold"}`}>
                  {note.message}
                </span>
                <span className="text-xs text-muted">
                  {timeAgo(note.created_at)}, {dateTime(note.created_at)}
                </span>
              </span>
              {!note.is_read && (
                <button
                  type="button"
                  onClick={() => markRead(note)}
                  className="btn-ghost min-h-0 shrink-0 px-2.5 py-1.5 text-sm"
                  aria-label={`Mark read: ${note.message}`}
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
        </ul>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}