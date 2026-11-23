import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, setSessionExpiredHandler } from "../api/client";
import { setCurrency } from "../format";
import { clearSession, loadSession, saveSession } from "./session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(() => loadSession()?.user || null);
  const [sessionExpired, setSessionExpired] = useState(false);
  // True after "Sign out": the next person should not be sent back to this person's page.
  const [signedOut, setSignedOut] = useState(false);

  // Money is shown in the business's own currency.
  useEffect(() => setCurrency(user?.business?.currency), [user]);

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

  const startSession = useCallback((session) => {
    saveSession({
      accessToken: session.access_token,
      refreshToken: session.refresh_token,
      user: session.user,
    });
    setSessionExpired(false);
    setSignedOut(false);
    setUser(session.user);
    return session.user;
  }, []);

  // Email + password. The backend answers with the tokens, which are kept for the next visit.
  const signIn = useCallback(
    async (email, password) =>
      startSession(
        await api("/api/auth/login", { method: "POST", body: { email, password }, auth: false }),
      ),
    [startSession],
  );

  // Join an existing business with its join code (the person then signs in).
  const register = useCallback(
    (fields) => api("/api/auth/register", { method: "POST", body: fields, auth: false }),
    [],
  );

  // Start a new business: its owner becomes the Administrator and is signed in at once.
  const registerBusiness = useCallback(
    async (fields) =>
      startSession(
        await api("/api/auth/register-business", { method: "POST", body: fields, auth: false }),
      ),
    [startSession],
  );

  // Ends the session on the server too, so a copied token stops working (US-04).
  const signOut = useCallback(() => {
    const hadSession = Boolean(loadSession()?.accessToken);
    const done = () => {
      clearSession();
      setSignedOut(true);
      setUser(null);
      navigate("/login", { replace: true });
    };
    if (!hadSession) return done();
    return api("/api/auth/logout", { method: "POST" })
      .catch(() => {})
      .finally(done);
  }, [navigate]);

  // Fetch the account again (after the business settings change, for example).
  const reloadUser = useCallback(async () => {
    const me = await api("/api/auth/me");
    saveSession({ ...loadSession(), user: me });
    setUser(me);
    return me;
  }, []);

  // After the person edits their profile: keep the new details for this visit and the next.
  const updateUser = useCallback((fresh) => {
    saveSession({ ...loadSession(), user: fresh });
    setUser(fresh);
  }, []);

  const hasRole = useCallback((...roles) => Boolean(user && roles.includes(user.role)), [user]);

  const value = useMemo(
    () => ({
      user,
      sessionExpired,
      signedOut,
      signIn,
      register,
      registerBusiness,
      signOut,
      hasRole,
      updateUser,
      reloadUser,
    }),
    [
      user,
      sessionExpired,
      signedOut,
      signIn,
      register,
      registerBusiness,
      signOut,
      hasRole,
      updateUser,
      reloadUser,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
