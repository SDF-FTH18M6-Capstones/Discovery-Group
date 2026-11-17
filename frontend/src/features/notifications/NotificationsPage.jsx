import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import { announceNotificationsChanged as announce } from "../../events";
import { dateTime } from "../../format";
import { notifications } from "../../store";

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
    <section className="flex max-w-3xl flex-col gap-4">
      <PageHeader title="Notifications" subtitle="Updates about your own work.">
        <button type="button" onClick={markAll} disabled={!unreadHere} className="btn-secondary">
          Mark all as read
        </button>
      </PageHeader>

      <div role="group" aria-label="Show" className="flex gap-2">
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
            className="chip"
          >
            {text}
          </button>
        ))}
      </div>

      {(error || list.error) && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}
      {list.status === "loading" && list.items.length === 0 && <SkeletonCards count={4} />}
      {list.status === "ready" && list.items.length === 0 && (
        <p className="card p-6 text-center text-muted">
          {unreadOnly ? "You are all caught up." : "No notifications yet."}
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {list.items.map((note) => (
          <li
            key={note.id}
            className={`card flex items-start gap-3 p-4 ${note.is_read ? "opacity-70" : "border-l-4 border-l-brand"}`}
          >
            <span className="min-w-0 flex-1">
              <span className={`block text-sm ${note.is_read ? "" : "font-semibold"}`}>
                {note.message}
              </span>
              <span className="text-xs text-muted">{dateTime(note.created_at)}</span>
            </span>
            {!note.is_read && (
              <button
                type="button"
                onClick={() => markRead(note)}
                className="link shrink-0 text-sm"
                aria-label={`Mark read: ${note.message}`}
              >
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
      <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
    </section>
  );
}