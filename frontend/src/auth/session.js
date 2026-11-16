// Where the signed-in session is kept between page loads.
// The access token lasts 15 minutes and the refresh token 7 days (set by the backend).
const KEY = "stockpilot.session";

export function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // Storage blocked (private window): the session lasts until the tab closes.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing stored
  }
}