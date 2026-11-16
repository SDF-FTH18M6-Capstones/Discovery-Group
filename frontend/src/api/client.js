import { clearSession, loadSession, saveSession } from "../auth/session";

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:5000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, message, details = {}) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

let onSessionExpired = () => {};
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

async function send(path, { method, body, token }) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
}

let refreshing = null; 

async function refreshAccessToken() {
  const session = loadSession();
  if (!session?.refreshToken) return null;
  refreshing ??= send("/api/auth/refresh", { method: "POST", token: session.refreshToken })
    .then(async (response) => {
      if (!response.ok) return null;
      const { access_token } = await response.json();
      saveSession({ ...loadSession(), accessToken: access_token });
      return access_token;
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
  const token = auth ? loadSession()?.accessToken : undefined;
  let response = await send(path, { method, body, token });

  if (response.status === 401 && token) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      response = await send(path, { method, body, token: fresh });
    }
    if (response.status === 401) {
      clearSession();
      onSessionExpired();
    }
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.error || {};
    throw new ApiError(response.status, error.message || "Request failed", error.details);
  }
  return data;
}
