import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt, userFor } from "./helpers";

const owner = userFor("admin", { platform_owner: true });

const overview = {
  businesses: 4,
  by_status: { trial: 1, active: 2, grace: 1, expired: 0, suspended: 0 },
  revenue_this_month: 3000,
  revenue_total: 9000,
  price: 1500,
  paybill_mode: "simulate",
  paybill_connected: false,
  subscriptions_required: false,
};

const mboga = {
  id: 7,
  name: "Mama Mboga",
  created_at: "2026-11-01T08:00:00Z",
  owner_email: "w@mboga.test",
  staff: 3,
  last_sale_at: "2026-11-26T15:00:00Z",
  status: "grace",
  ends_on: "2026-11-24",
  paid_until: "2026-11-24",
  is_active: true,
};

const bodyOf = (spy, path) => {
  const call = spy.mock.calls.find(
    ([url, options]) => new URL(url).pathname === path && options?.method !== undefined,
  );
  return call && JSON.parse(call[1].body);
};

function platformApi(extra = {}) {
  return mockApi(
    {
      "GET /api/platform/overview": [200, overview],
      "GET /api/platform/businesses": [200, page([mboga])],
      "GET /api/platform/payments": [
        200,
        page([
          {
            id: 1,
            business_id: 7,
            business_name: "Mama Mboga",
            months: 3,
            amount: 4500,
            receipt_number: "QKT123",
            simulated: false,
            completed_at: "2026-11-20T10:00:00Z",
          },
        ]),
      ],
      ...extra,
    },
    owner,
  );
}

describe("platform console", () => {
  it("is only in the menu for StockPilot's owners", async () => {
    mockApi({}, owner);
    renderAt("/", { as: owner });

    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Platform" })).toHaveAttribute(
      "href",
      "/platform",
    );
  });

  it("is hidden from a business administrator", async () => {
    mockApi({}, "admin");
    renderAt("/platform", { as: "admin" });

    expect(await screen.findByText("Page not found")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).queryByRole("link", { name: "Platform" })).toBeNull();
  });

  it("shows businesses, takings and the Paybill status", async () => {
    platformApi();
    renderAt("/platform", { as: owner });

    expect(await screen.findByText("KES 3,000")).toBeInTheDocument();
    expect(screen.getByText("2 paying, 1 on trial")).toBeInTheDocument();
    expect(screen.getByTestId("paybill-status")).toHaveTextContent("Test mode");
    const row = (await screen.findByText("w@mboga.test")).closest("tr");
    expect(within(row).getByText("Payment due")).toBeInTheDocument();
    expect(screen.getByText("QKT123")).toBeInTheDocument();
  });

  it("adds free months with a reason", async () => {
    const spy = platformApi({
      "POST /api/platform/businesses/7/extend": [200, { ...mboga, status: "active" }],
    });
    const user = userEvent.setup();
    renderAt("/platform", { as: owner });

    const row = (await screen.findByText("w@mboga.test")).closest("tr");
    await user.click(within(row).getByRole("button", { name: "Add months" }));
    await user.selectOptions(within(row).getByLabelText("Months"), "3");
    await user.type(within(row).getByLabelText("Why"), "Paid in cash");
    await user.click(within(row).getByRole("button", { name: "Add months" }));

    await waitFor(() =>
      expect(bodyOf(spy, "/api/platform/businesses/7/extend")).toEqual({
        months: 3,
        note: "Paid in cash",
      }),
    );
  });

  it("suspends a business and shows why it failed when it does", async () => {
    platformApi({
      "POST /api/platform/businesses/7/suspend": [
        409,
        { error: { code: 409, message: "You cannot suspend your own business." } },
      ],
    });
    const user = userEvent.setup();
    renderAt("/platform", { as: owner });

    const row = (await screen.findByText("w@mboga.test")).closest("tr");
    await user.click(within(row).getByRole("button", { name: "Suspend" }));
    await user.type(within(row).getByLabelText("Reason"), "Testing");
    await user.click(within(row).getByRole("button", { name: "Suspend" }));

    expect(
      await within(row).findByText("You cannot suspend your own business."),
    ).toBeInTheDocument();
  });

  it("changes the monthly price", async () => {
    const spy = platformApi({
      "PUT /api/platform/price": [200, { ...overview, price: 2000 }],
    });
    const user = userEvent.setup();
    renderAt("/platform", { as: owner });

    const price = await screen.findByLabelText("Monthly price (KES)");
    await user.clear(price);
    await user.type(price, "2000");
    await user.click(screen.getByRole("button", { name: "Save price" }));

    expect(await screen.findByText("New payments use the new price.")).toBeInTheDocument();
    expect(bodyOf(spy, "/api/platform/price")).toEqual({ price: 2000 });
  });
});
