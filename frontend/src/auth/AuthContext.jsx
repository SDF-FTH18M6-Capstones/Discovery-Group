// Who is signed in, shared with the whole app through React Context.
//   const { user, signIn, register, signOut, hasRole } = useAuth();
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, setSessionExpiredHandler } from "../api/client";
import { clearSession, loadSession, saveSession } from "./session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(() => loadSession()?.user || null);
  const [sessionExpired, setSessionExpired] = useState(false);

  // When a request finds the session has expired, forget the user. <RequireAuth> then
  // sends them to /login, which shows "Your session has expired".
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setSessionExpired(true);
      setUser(null);
    });
  }, []);

  // On page load, confirm the stored session is still valid and refresh the user's details.
  useEffect(() => {
    if (!loadSession()?.accessToken) return;
    api("/api/auth/me")
      .then((me) => {
        saveSession({ ...loadSession(), user: me });
        setUser(me);
      })
      .catch(() => {});
  }, []);

  // Email + password. The backend answers with the tokens, which are kept for the next visit.
  const signIn = useCallback(async (email, password) => {
    const session = await api("/api/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    saveSession({
      accessToken: session.access_token,
      refreshToken: session.refresh_token,
      user: session.user,
    });
    setSessionExpired(false);
    setUser(session.user);
    return session.user;
  }, []);

  const register = useCallback(
    (fields) => api("/api/auth/register", { method: "POST", body: fields, auth: false }),
    [],
  );

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const hasRole = useCallback((...roles) => Boolean(user && roles.includes(user.role)), [user]);

  const value = useMemo(
    () => ({ user, sessionExpired, signIn, register, signOut, hasRole }),
    [user, sessionExpired, signIn, register, signOut, hasRole],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}