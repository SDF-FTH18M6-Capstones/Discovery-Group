import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, renderAt, userFor } from "./helpers";

const overview = {
  status: "trial",
  required: true,
  trial_ends_on: "2026-12-11",
  paid_until: null,
  ends_on: "2026-12-11",
  grace_until: "2026-12-18",
  days_left: 14,
  read_only: false,
  price: 1500,
  plans: [1, 3, 6, 12],
  online_payment: true,
  payments: [],
};

const pending = {
  id: 4,
  purpose: "subscription",
  status: "pending",
  amount: 4500,
  months: 3,
  simulated: true,
};

const withPlan = (subscription) =>
  userFor("admin", {
    business: { id: 1, name: "Test Shop", currency: "KES", subscription },
  });

describe("billing", () => {
  it("lets the administrator pay for months ahead by M-Pesa", async () => {
    let paid = false;
    const spy = mockApi(
      {
        "GET /api/billing": () => [
          200,
          paid
            ? {
                ...overview,
                status: "active",
                paid_until: "2027-03-11",
                ends_on: "2027-03-11",
                days_left: 104,
                payments: [
                  {
                    ...pending,
                    status: "paid",
                    receipt_number: "SIM0000004",
                    completed_at: "2026-11-27T10:00:00Z",
                  },
                ],
              }
            : overview,
        ],
        "POST /api/billing/pay": [201, pending],
        "POST /api/billing/payments/4/simulate": () => {
          paid = true;
          return [200, { ...pending, status: "paid", receipt_number: "SIM0000004" }];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/billing", { as: "admin" });

    expect(await screen.findByTestId("billing-status")).toHaveTextContent("Free trial");
    await user.click(screen.getByText("3 months"));
    await user.type(screen.getByLabelText("M-Pesa number to pay from"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Pay KES 4,500" }));
    expect(await screen.findByText("Check your phone")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pay (test mode)" }));

    expect(await screen.findByText(/M-Pesa receipt SIM0000004/)).toBeInTheDocument();
    expect(screen.getByTestId("billing-status")).toHaveTextContent("Active");
    const call = spy.mock.calls.find(([url]) => url.endsWith("/api/billing/pay"));
    expect(JSON.parse(call[1].body)).toEqual({ months: 3, phone: "0712345678" });
  });

  it("explains when online payment is not open yet", async () => {
    mockApi({ "GET /api/billing": [200, { ...overview, online_payment: false }] }, "admin");
    renderAt("/billing", { as: "admin" });

    expect(await screen.findByText(/Contact StockPilot to renew/)).toBeInTheDocument();
  });

  it("warns everyone when the subscription has ended", async () => {
    const ended = withPlan({ status: "expired", required: true, days_left: -9, read_only: true });
    mockApi({}, ended);
    renderAt("/", { as: ended });

    const banner = await screen.findByText(/changes are paused/);
    expect(within(banner.parentElement).getByRole("link", { name: "Renew now" })).toHaveAttribute(
      "href",
      "/billing",
    );
  });

  it("tells staff to ask the administrator", async () => {
    const staff = userFor("sales", {
      business: {
        id: 1,
        name: "Test Shop",
        currency: "KES",
        subscription: { status: "trial", required: true, days_left: 2, read_only: false },
      },
    });
    mockApi({}, staff);
    renderAt("/", { as: staff });

    expect(await screen.findByText("Your free trial ends in 2 days.")).toBeInTheDocument();
    expect(screen.getByText("Ask your administrator to renew it.")).toBeInTheDocument();
  });

  it("stays quiet while there is plenty of time", async () => {
    const fine = withPlan({ status: "trial", required: true, days_left: 10, read_only: false });
    mockApi({}, fine);
    renderAt("/", { as: fine });

    await screen.findByRole("navigation", { name: "Main" });
    expect(screen.queryByText(/free trial ends/)).toBeNull();
  });
});

describe("M-Pesa settings", () => {
  it("lets the administrator connect their own Paybill without showing the keys again", async () => {
    const saved = {
      mode: "sandbox",
      type: "paybill",
      shortcode: "174379",
      till: null,
      has_passkey: true,
      has_keys: true,
    };
    const spy = mockApi(
      {
        "GET /api/business": [
          200,
          {
            id: 1,
            name: "Test Shop",
            timezone: "Africa/Nairobi",
            currency: "KES",
            vat_rate: "16.00",
            join_code: "ABCD2345",
          },
        ],
        "GET /api/business/mpesa": [
          200,
          {
            mode: "simulate",
            type: "paybill",
            shortcode: null,
            till: null,
            has_passkey: false,
            has_keys: false,
          },
        ],
        "PUT /api/business/mpesa": [200, saved],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "admin" });

    await user.click(await screen.findByLabelText(/Safaricom sandbox/));
    await user.type(screen.getByLabelText("Paybill number"), "174379");
    await user.type(screen.getByLabelText("Passkey"), "pk");
    await user.type(screen.getByLabelText("Consumer key"), "ck");
    await user.type(screen.getByLabelText("Consumer secret"), "cs");
    await user.click(screen.getByRole("button", { name: "Save M-Pesa settings" }));

    expect(await screen.findByText("M-Pesa settings saved.")).toBeInTheDocument();
    const call = spy.mock.calls.find(
      ([url, options]) => url.endsWith("/api/business/mpesa") && options?.method === "PUT",
    );
    expect(JSON.parse(call[1].body)).toEqual({
      mode: "sandbox",
      type: "paybill",
      shortcode: "174379",
      till: null,
      passkey: "pk",
      consumer_key: "ck",
      consumer_secret: "cs",
    });
    expect(screen.getByLabelText("Consumer key")).toHaveValue("");
    expect(screen.getByLabelText("Consumer key")).toHaveAttribute(
      "placeholder",
      "Saved. Leave empty to keep it.",
    );
  });
});
