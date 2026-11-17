import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ErrorBoundary from "../components/ErrorBoundary";
import { mockApi, page, renderAt } from "./helpers";

describe("look and feel", () => {
  it("switches to dark mode and remembers it", async () => {
    mockApi({}, "employee");
    const user = userEvent.setup();
    renderAt("/", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "Switch to dark mode" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("stockpilot.theme")).toBe("dark");
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("shows a banner instead of a blank page when a page crashes", () => {
    function Broken() {
      throw new Error("boom");
    }
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on this page");
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
  });
});

describe("optimistic requests", () => {
  const pending = {
    id: 7,
    item: "Printer paper",
    quantity: 2,
    urgency: "normal",
    reason: "Reports",
    status: "pending",
    requester_id: 99,
    requester_name: "Alex Kamau",
    created_at: "2026-11-10T09:00:00Z",
  };

  it("put a refused approval back to pending", async () => {
    mockApi(
      {
        "GET /api/requests/": [200, page([pending])],
        "POST /api/requests/7/approve": [
          409,
          { error: { code: 409, message: "This request was already decided." } },
        ],
      },
      "procurement",
    );
    const user = userEvent.setup();
    renderAt("/approvals", { as: "procurement" });

    await user.click(await screen.findByRole("button", { name: "Open request for Printer paper" }));
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This request was already decided.");
    const row = screen
      .getByRole("button", { name: "Open request for Printer paper" })
      .closest("tr");
    expect(within(row).getByText("Pending")).toBeInTheDocument();
  });

  it("bring back a request the server would not withdraw", async () => {
    mockApi(
      {
        "GET /api/requests/": [200, page([{ ...pending, requester_id: 1 }])],
        "DELETE /api/requests/7": [
          409,
          { error: { code: 409, message: "Only pending requests can be withdrawn." } },
        ],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "Withdraw" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only pending requests can be withdrawn.",
    );
    expect(screen.getByText("Printer paper × 2")).toBeInTheDocument();
  });
});
