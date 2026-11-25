import { clearSession, loadSession, saveSession } from "../auth/session";

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:5000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, message, details = {}, reason = "") {
    super(message);
    this.status = status;
    this.details = details;
    this.reason = reason;
  }
}

let onSessionExpired = () => {};
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

async function send(path, { method, body, token }) {
  const headers = {};
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
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

async function authorised(path, { method, body, auth }) {
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
  return response;
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
  const response = await authorised(path, { method, body, auth });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.error || {};
    throw new ApiError(
      response.status,
      error.message || "Request failed",
      error.details,
      error.reason || "",
    );
  }
  return data;
}

export function upload(path, file, field = "photo") {
  const form = new FormData();
  form.append(field, file);
  return api(path, { method: "POST", body: form });
}

export async function download(path, filename) {
  const response = await authorised(path, { method: "GET", auth: true });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.error?.message || "Download failed");
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export const mediaUrl = (url) => (url && url.startsWith("/api/") ? `${API_URL}${url}` : url || "");

export const newIdempotencyKey = () =>
  globalThis.crypto?.randomUUID?.() ||
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
