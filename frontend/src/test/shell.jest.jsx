import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "../App";
import { makeStore } from "../store";

function renderAt(path) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </Provider>,
  );
}

describe("app shell", () => {
  it("shows the API as up when /api/health answers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok", database: "ok" }),
    });
    renderAt("/status");

    expect(await screen.findByText("API is up · database ok")).toBeInTheDocument();
  });

  it("explains the problem when the backend is not running", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderAt("/status");

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("shows a not-found page for unknown addresses", () => {
    renderAt("/nowhere");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("has links to every section", () => {
    renderAt("/nowhere");

    for (const name of ["Products", "Suppliers", "System status"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
  });
});