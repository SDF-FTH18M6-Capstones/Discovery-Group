import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ROLE_NAMES, ROLES } from "../../auth/roles";
import Pagination from "../../components/Pagination";
import { Avatar } from "../../components/ui";
import { users } from "../../store";

function Waiting({ person, onDone }) {
  const [role, setRole] = useState("employee");
  const [busy, setBusy] = useState(false);

  const decide = async (action) => {
    setBusy(true);
    try {
      if (action === "approve") {
        await api(`/api/users/${person.id}/approve`, { method: "POST", body: { role } });
        onDone(`${person.full_name} can sign in now as ${ROLE_NAMES[role]}.`, null);
      } else {
        await api(`/api/users/${person.id}/decline`, { method: "POST" });
        onDone(`${person.full_name}'s request was declined.`, null);
      }
    } catch (err) {
      setBusy(false);
      onDone(null, err.message);
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-3 first:border-t-0">
      <Avatar name={person.full_name} size={30} />
      <span className="flex min-w-40 flex-1 flex-col">
        <span className="font-semibold">{person.full_name}</span>
        <span className="text-sm text-muted">
          {person.email}
          {!person.email_verified && " · email not confirmed yet"}
        </span>
      </span>
      <label htmlFor={`waiting-role-${person.id}`} className="sr-only">
        Role to give {person.full_name}
      </label>
      <select
        id={`waiting-role-${person.id}`}
        value={role}
        onChange={(event) => setRole(event.target.value)}
        className="input w-auto px-2"
      >
        {ROLES.map((value) => (
          <option key={value} value={value}>
            {ROLE_NAMES[value]}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={busy}
        onClick={() => decide("approve")}
        className="btn-primary"
        aria-label={`Approve ${person.full_name}`}
      >
        Approve
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => decide("decline")}
        className="btn-ghost text-danger"
        aria-label={`Decline ${person.full_name}`}
      >
        Decline
      </button>
    </li>
  );
}

function RoleCell({ person, isYou, onChanged }) {
  const [role, setRole] = useState(person.role);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const updated = await api(`/api/users/${person.id}/role`, { method: "PUT", body: { role } });
      onChanged(`${updated.full_name} is now ${ROLE_NAMES[updated.role]}.`, null);
    } catch (error) {
      onChanged(null, error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={`role-${person.id}`} className="sr-only">
        Role for {person.full_name}
      </label>
      <select
        id={`role-${person.id}`}
        value={role}
        disabled={isYou}
        onChange={(event) => setRole(event.target.value)}
        className="input h-9 px-2 disabled:opacity-60"
      >
        {ROLES.map((value) => (
          <option key={value} value={value}>
            {ROLE_NAMES[value]}
          </option>
        ))}
      </select>
      {!isYou && (
        <button
          type="button"
          disabled={busy || role === person.role}
          onClick={save}
          aria-label={`Save role for ${person.full_name}`}
          className="btn-primary px-3 py-1 text-sm"
        >
          Save
        </button>
      )}
    </div>
  );
}

function ActiveCell({ person, isYou, onChanged }) {
  const [busy, setBusy] = useState(false);
  if (isYou) return <span className="text-sm text-muted">Active</span>;

  const toggle = async () => {
    const verb = person.is_active ? "deactivate" : "reactivate";
    if (
      person.is_active &&
      !window.confirm(
        `Deactivate ${person.full_name}? They are signed out at once and cannot sign in. Their sales, requests and approvals stay on record.`,
      )
    )
      return;
    setBusy(true);
    try {
      const updated = await api(`/api/users/${person.id}/${verb}`, { method: "POST" });
      onChanged(
        `${updated.full_name} is ${updated.is_active ? "active again" : "deactivated"}.`,
        null,
      );
    } catch (error) {
      onChanged(null, error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${person.is_active ? "bg-mint text-brand-dark" : "bg-danger-soft text-danger"}`}
      >
        {person.is_active ? "Active" : "Deactivated"}
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={toggle}
        aria-label={`${person.is_active ? "Deactivate" : "Reactivate"} ${person.full_name}`}
        className={`${person.is_active ? "btn-ghost text-danger" : "btn-secondary"} px-3 py-1 text-sm`}
      >
        {person.is_active ? "Deactivate" : "Reactivate"}
      </button>
    </div>
  );
}

export default function UsersPage() {
  const dispatch = useDispatch();
  const { user } = useAuth();
  const list = useSelector((state) => state.users);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [waiting, setWaiting] = useState([]);

  const loadWaiting = () =>
    api("/api/users/?pending=true&per_page=50")
      .then((result) => setWaiting(result.results))
      .catch(() => {});

  useEffect(() => {
    loadWaiting();
  }, []);

  useEffect(() => {
    dispatch(users.fetchList({ search, role, active, pending: false, page, per_page: 10 }));
  }, [dispatch, search, role, active, page]);

  const changed = (message, failure) => {
    setNotice(message || "");
    setError(failure || "");
    if (message) {
      loadWaiting();
      dispatch(users.fetchList({ search, role, active, pending: false, page, per_page: 10 }));
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="page-title">Users and roles</h1>
        <p className="text-muted">
          Staff join with your business's code (see Settings). They can sign in once you approve
          them and choose their role. Change a role here at any time; deactivate people who leave.
        </p>
      </div>

      {waiting.length > 0 && (
        <section aria-labelledby="waiting-title" className="panel overflow-hidden">
          <h2
            id="waiting-title"
            className="flex items-center gap-2 border-b border-line bg-warn-soft px-4 py-3 text-sm font-semibold text-warn"
          >
            Waiting for your approval ({waiting.length})
          </h2>
          <ul>
            {waiting.map((person) => (
              <Waiting key={person.id} person={person} onDone={changed} />
            ))}
          </ul>
        </section>
      )}

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="text-danger">
          {error || list.error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <label htmlFor="user-search" className="sr-only">
          Search users
        </label>
        <input
          id="user-search"
          type="search"
          placeholder="Name or email"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          className="input w-full max-w-sm"
        />
        <label htmlFor="user-role" className="sr-only">
          Filter by role
        </label>
        <select
          id="user-role"
          value={role}
          onChange={(event) => {
            setRole(event.target.value);
            setPage(1);
          }}
          className="input px-2"
        >
          <option value="">All roles</option>
          {ROLES.map((value) => (
            <option key={value} value={value}>
              {ROLE_NAMES[value]}
            </option>
          ))}
        </select>
        <label htmlFor="user-active" className="sr-only">
          Filter by status
        </label>
        <select
          id="user-active"
          value={active}
          onChange={(event) => {
            setActive(event.target.value);
            setPage(1);
          }}
          className="input px-2"
        >
          <option value="">Active and deactivated</option>
          <option value="true">Active only</option>
          <option value="false">Deactivated only</option>
        </select>
      </div>

      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Access</th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((person) => (
              <tr
                key={`${person.id}-${person.role}-${person.is_active}`}
                className={`border-t border-line ${person.is_active === false ? "opacity-70" : ""}`}
              >
                <td className="px-4 py-3 font-semibold">
                  <Avatar name={person.full_name} size={30} className="mr-3 align-middle" />
                  {person.full_name}
                  {person.id === user.id && <span className="font-normal text-muted"> (you)</span>}
                </td>
                <td className="px-4 py-3">
                  {person.email}
                  {person.email_verified === false && (
                    <span
                      className="ml-2 rounded-full bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn"
                      title="This person has not opened the confirmation link yet, so they cannot sign in."
                    >
                      Unconfirmed
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <RoleCell person={person} isYou={person.id === user.id} onChanged={changed} />
                </td>
                <td className="px-4 py-3">
                  <ActiveCell person={person} isYou={person.id === user.id} onChanged={changed} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
      <p className="text-xs text-muted">
        You cannot change your own role or deactivate yourself, so there is always an administrator.
        Every role change and deactivation is written to the audit log.
      </p>
    </section>
  );
}
