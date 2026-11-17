import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, renderAt } from "./helpers";

describe("landing page", () => {
  it("greets visitors and leads to sign in and sign up", async () => {
    mockApi({});
    renderAt("/");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Know what is on every shelf, to the last unit.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Create an account" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getAllByRole("link", { name: "Sign in" })[0]).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
  });

  it("explains each role when it is chosen", async () => {
    mockApi({});
    const user = userEvent.setup();
    renderAt("/");

    await user.click(screen.getByRole("button", { name: "Sales attendant" }));

    expect(screen.getByRole("button", { name: "Sales attendant" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText(/Rings up sales on the till/)).toBeInTheDocument();
  });

  it("is replaced by the dashboard once signed in", async () => {
    mockApi({}, "employee");
    renderAt("/", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Welcome, Test" })).toBeInTheDocument();
    expect(screen.queryByText(/Know what is on every shelf/)).toBeNull();
  });
});
