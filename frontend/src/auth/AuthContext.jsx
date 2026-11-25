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
  const [signedOut, setSignedOut] = useState(false);

  useEffect(() => setCurrency(user?.business?.currency), [user]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setSessionExpired(true);
      setUser(null);
    });
  }, []);

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

  const signIn = useCallback(
    async (email, password) => {
      const answer = await api("/api/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      if (answer.code_required) return { challenge: answer };
      return { user: startSession(answer) };
    },
    [startSession],
  );

  const verifyCode = useCallback(
    async (challengeId, code) =>
      startSession(
        await api("/api/auth/login/verify", {
          method: "POST",
          body: { challenge_id: challengeId, code },
          auth: false,
        }),
      ),
    [startSession],
  );

  const resendCode = useCallback(
    (challengeId) =>
      api("/api/auth/login/resend", {
        method: "POST",
        body: { challenge_id: challengeId },
        auth: false,
      }),
    [],
  );

  const register = useCallback(
    (fields) => api("/api/auth/register", { method: "POST", body: fields, auth: false }),
    [],
  );

  const registerBusiness = useCallback(
    async (fields) => {
      const answer = await api("/api/auth/register-business", {
        method: "POST",
        body: fields,
        auth: false,
      });
      if (answer.verification_required) return { message: answer.message };
      return { user: startSession(answer) };
    },
    [startSession],
  );

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

  const reloadUser = useCallback(async () => {
    const me = await api("/api/auth/me");
    saveSession({ ...loadSession(), user: me });
    setUser(me);
    return me;
  }, []);

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
      verifyCode,
      resendCode,
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
      verifyCode,
      resendCode,
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
