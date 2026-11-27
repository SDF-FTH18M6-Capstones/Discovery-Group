import { render } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { saveSession } from "../auth/session";
import { makeStore } from "../store";
import { ThemeProvider } from "../theme/ThemeContext";

export const page = (results) => ({
  results,
  count: results.length,
  page: 1,
  per_page: 10,
  pages: 1,
});

export const userFor = (role, extra = {}) => ({
  id: 1,
  full_name: `Test ${role}`,
  email: `${role}@test.com`,
  role,
  covers: [],
  ...extra,
});

export const soleOwner = () => userFor("admin", { covers: ["procurement", "inventory", "sales"] });

const asUser = (who) => (typeof who === "string" ? userFor(who) : who);

export function mockApi(routes = {}, role = null) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const key = `${options.method || "GET"} ${new URL(url).pathname}`;
    const answer = routes[key];
    const [status, body] =
      typeof answer === "function"
        ? answer(options, new URL(url))
        : answer || (key === "GET /api/auth/me" && role ? [200, asUser(role)] : [200, page([])]);
    return { ok: status < 400, status, json: async () => body };
  });
}

export function renderAt(path, { as = null } = {}) {
  if (as) {
    saveSession({ accessToken: "test-access", refreshToken: "test-refresh", user: asUser(as) });
  }
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </AuthProvider>
      </MemoryRouter>
    </Provider>,
  );
}
