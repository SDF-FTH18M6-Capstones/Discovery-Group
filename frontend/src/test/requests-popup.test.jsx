import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const pending = {
  id: 7,
  item: "Printer paper",
  quantity: 2,
  urgency: "normal",
  reason: "Monthly reports",
  status: "pending",
  requester_id: 1,
  created_at: "2026-11-16T08:00:00Z",
};

const bodyOf = (spy, method, path) => {
  const call = spy.mock.calls.find(
    ([url, options]) => options?.method === method && new URL(url).pathname === path,
  );
  return call && JSON.parse(call[1].body);
};

describe("request pop-ups", () => {
  it("open the new request form over the page and close with Escape", async () => {
    mockApi({}, "employee");
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    const opener = await screen.findByRole("button", { name: "New request" });
    await user.click(opener);

    const dialog = screen.getByRole("dialog", { name: "New request" });
    expect(within(dialog).getByLabelText("What do you need?")).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opener).toHaveFocus();
  });

  it("open straight away from the dashboard's New request (?new=1)", async () => {
    mockApi({}, "employee");
    renderAt("/requests?new=1", { as: "employee" });

    expect(await screen.findByRole("dialog", { name: "New request" })).toBeInTheDocument();
  });

  it("show a request to read, and edit it from there", async () => {
    const spy = mockApi(
      {
        "GET /api/requests/": [200, page([pending])],
        "PUT /api/requests/7": [200, { ...pending, quantity: 5 }],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "View request for Printer paper" }));
    const view = screen.getByRole("dialog", { name: "Printer paper × 2" });
    expect(within(view).getByText("REQ-0007")).toBeInTheDocument();
    expect(within(view).getByText("Monthly reports")).toBeInTheDocument();

    await user.click(within(view).getByRole("button", { name: "Edit" }));
    const form = screen.getByRole("dialog", { name: "Edit request" });
    await user.clear(within(form).getByLabelText("Quantity"));
    await user.type(within(form).getByLabelText("Quantity"), "5");
    await user.click(within(form).getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Request updated.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(bodyOf(spy, "PUT", "/api/requests/7")).toMatchObject({ quantity: 5 });
  });

  it("ask before cancelling, and Keep it changes nothing", async () => {
    const spy = mockApi({ "GET /api/requests/": [200, page([pending])] }, "employee");
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "View request for Printer paper" }));
    await user.click(screen.getByRole("button", { name: "Cancel request" }));
    expect(screen.getByText("Cancel this request?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep it" }));

    expect(screen.getByRole("button", { name: "Cancel request" })).toBeInTheDocument();
    await waitFor(() =>
      expect(spy.mock.calls.some(([url]) => url.endsWith("/cancel"))).toBe(false),
    );
  });
});
