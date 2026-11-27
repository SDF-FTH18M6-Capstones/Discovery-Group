import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const tea = {
  id: 1,
  sku: "SP-001",
  name: "Tea",
  category_name: "Beverages",
  cost_price: "80.00",
  selling_price: "120.00",
  quantity: 5,
  reorder_level: 1,
};

const pending = {
  id: 3,
  status: "pending",
  phone: "254712345678",
  amount: 120,
  simulated: true,
  receipt_number: null,
  result_desc: null,
  problem: null,
  sale_id: null,
};

const sale = {
  id: 9,
  receipt_number: "S-0009",
  payment_method: "mpesa",
  payment_reference: "QKT1ABC2DE",
  total: "120.00",
  vat_rate: "16.00",
  vat_amount: "16.55",
  net_amount: "103.45",
  attendant_name: "Test sales",
  created_at: "2026-11-27T09:00:00Z",
  items: [
    { product_id: 1, product_name: "Tea", quantity: 1, unit_price: "120.00", line_total: "120.00" },
  ],
};

const bodyOf = (spy, method, path) => {
  const call = spy.mock.calls.find(
    ([url, options]) => new URL(url).pathname === path && options?.method === method,
  );
  return call && JSON.parse(call[1].body);
};

async function ringUpTea(user) {
  await user.click(await screen.findByRole("button", { name: "Add Tea" }));
  await user.click(screen.getByText("M-Pesa"));
}

describe("M-Pesa at the till", () => {
  it("sends a prompt to the customer's phone and completes the sale when they pay", async () => {
    const spy = mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/payments/mpesa/config": [200, { mode: "simulate", enabled: true }],
        "POST /api/payments/mpesa": [201, pending],
        "POST /api/payments/mpesa/3/simulate": [
          200,
          { ...pending, status: "paid", sale_id: 9, receipt_number: "QKT1ABC2DE" },
        ],
        "GET /api/sales/9": [200, sale],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await ringUpTea(user);
    const send = await screen.findByRole("button", { name: "Send M-Pesa request" });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText("Customer's M-Pesa number"), "0712 345 678");
    await user.click(send);

    expect(await screen.findByText("Waiting for the customer to pay")).toBeInTheDocument();
    expect(screen.getByText(/KES 120 to 254712345678/)).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/payments/mpesa")).toEqual({
      phone: "0712 345 678",
      items: [{ product_id: 1, quantity: 1 }],
      idempotency_key: expect.any(String),
    });
    await user.click(screen.getByRole("button", { name: "Customer pays" }));

    expect(await screen.findByText(/Sale S-0009 saved/)).toBeInTheDocument();
    expect(screen.getByText(/M-Pesa \(QKT1ABC2DE\)/)).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/sales/")).toBeUndefined();
  });

  it("says why when the customer cancels, and keeps the cart", async () => {
    mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/payments/mpesa/config": [200, { mode: "simulate", enabled: true }],
        "POST /api/payments/mpesa": [201, pending],
        "POST /api/payments/mpesa/3/simulate": [
          200,
          {
            ...pending,
            status: "cancelled",
            result_desc: "The customer cancelled the M-Pesa prompt.",
          },
        ],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await ringUpTea(user);
    await user.type(await screen.findByLabelText("Customer's M-Pesa number"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Send M-Pesa request" }));
    await user.click(await screen.findByRole("button", { name: "Customer cancels" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The customer cancelled the M-Pesa prompt.",
    );
    expect(screen.getByTestId("qty-1")).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: "Send M-Pesa request" })).toBeEnabled();
  });

  it("follows a live payment until Safaricom confirms it", async () => {
    let checks = 0;
    mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/payments/mpesa/config": [200, { mode: "sandbox", enabled: true }],
        "POST /api/payments/mpesa": [201, { ...pending, simulated: false }],
        "GET /api/payments/mpesa/3": () => {
          checks += 1;
          return [200, { ...pending, simulated: false, status: "paid", sale_id: 9 }];
        },
        "GET /api/sales/9": [200, sale],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await ringUpTea(user);
    await user.type(await screen.findByLabelText("Customer's M-Pesa number"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Send M-Pesa request" }));

    expect(screen.queryByRole("button", { name: "Customer pays" })).toBeNull();
    expect(await screen.findByText(/Sale S-0009 saved/, {}, { timeout: 4000 })).toBeInTheDocument();
    expect(checks).toBe(1);
  });

  it("explains money received for stock that ran out", async () => {
    const problem =
      "M-Pesa QKT1 for 120 was received, but the sale could not be completed: Not enough stock: Tea (0 left). Sell it again or refund the customer.";
    mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/payments/mpesa/config": [200, { mode: "simulate", enabled: true }],
        "POST /api/payments/mpesa": [201, pending],
        "POST /api/payments/mpesa/3/simulate": [200, { ...pending, status: "paid", problem }],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await ringUpTea(user);
    await user.type(await screen.findByLabelText("Customer's M-Pesa number"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Send M-Pesa request" }));
    await user.click(await screen.findByRole("button", { name: "Customer pays" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Sell it again or refund");
  });

  it("records M-Pesa by hand when prompts are switched off", async () => {
    mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/payments/mpesa/config": [200, { mode: "off", enabled: false }],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await ringUpTea(user);

    expect(screen.queryByLabelText("Customer's M-Pesa number")).toBeNull();
    expect(screen.getByRole("button", { name: "Complete sale" })).toBeEnabled();
  });
});
