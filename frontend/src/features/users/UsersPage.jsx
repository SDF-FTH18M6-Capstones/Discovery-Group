import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ROLE_NAMES, ROLES } from "../../auth/roles";
import Pagination from "../../components/Pagination";
import { Avatar } from "../../components/ui";
import { users } from "../../store";

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

export default function UsersPage() {
  const dispatch = useDispatch();
  const { user } = useAuth();
  const list = useSelector((state) => state.users);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    dispatch(users.fetchList({ search, role, page, per_page: 10 }));
  }, [dispatch, search, role, page]);

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="page-title">Users and roles</h1>
        <p className="text-muted">
          Everyone signs up as an Employee. Change a role here; it applies from their next request.
        </p>
      </div>

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
      </div>

      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((person) => (
              <tr key={`${person.id}-${person.role}`} className="border-t border-line">
                <td className="px-4 py-3 font-semibold">
                  <Avatar name={person.full_name} size={30} className="mr-3 align-middle" />
                  {person.full_name}
                  {person.id === user.id && <span className="font-normal text-muted"> (you)</span>}
                </td>
                <td className="px-4 py-3">{person.email}</td>
                <td className="px-4 py-3">
                  <RoleCell
                    person={person}
                    isYou={person.id === user.id}
                    onChanged={(message, failure) => {
                      setNotice(message || "");
                      setError(failure || "");
                      if (message) dispatch(users.fetchList({ search, role, page, per_page: 10 }));
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
      <p className="text-xs text-muted">
        You cannot change your own role, so there is always an administrator.
      </p>
    </section>
  );
}