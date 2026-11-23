import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { code128Modules } from "../components/Barcode";
import { toCsv } from "../csv";
import { mockApi, page, renderAt } from "./helpers";

const bodyOf = (spy, method, path) => {
  const call = spy.mock.calls.find(
    ([url, options]) => options?.method === method && new URL(url).pathname === path,
  );
  return call && JSON.parse(call[1].body);
};

describe("barcodes (US-33)", () => {
  it("encode Code 128 with start, checksum and stop", () => {
    // Checked against an independent encoder (python-barcode) for the same text.
    expect(code128Modules("Ab-x!")).toBe(
      "110100100001010001100010010000110100110111001111001001011001101100100011101101100011101011",
    );
  });

  it("are drawn on the asset page with the code beneath", async () => {
    const asset = {
      id: 3,
      asset_code: "AST-0003",
      barcode: "SP0001000003",
      name: "Laptop",
      status: "available",
      condition: "good",
    };
    mockApi({ "GET /api/assets/": [200, page([asset])] }, "inventory");
    const user = userEvent.setup();
    renderAt("/assets", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "View Laptop" }));

    const dialog = screen.getByRole("dialog", { name: "Laptop" });
    expect(within(dialog).getByRole("img", { name: "Barcode SP0001000003" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Print label" })).toBeInTheDocument();
  });
});

describe("CSV export (US-31, US-41)", () => {
  it("quotes text and never lets a cell run as a formula", () => {
    const csv = toCsv(
      [
        { label: "Product", value: (r) => r.name },
        { label: "Change", value: (r) => r.change },
      ],
      [
        { name: 'Tea, "large"', change: -2 },
        { name: "=HYPERLINK(evil)", change: 5 },
      ],
    );

    expect(csv.split("\r\n")).toEqual([
      "Product,Change",
      '"Tea, ""large""",-2',
      "'=HYPERLINK(evil),5",
    ]);
  });
});

describe("voiding a sale (US-29)", () => {
  const sale = {
    id: 5,
    receipt_number: "S-0005",
    status: "completed",
    payment_method: "cash",
    total: "120.00",
    vat_rate: "16.00",
    vat_amount: "16.55",
    net_amount: "103.45",
    attendant_name: "Vincent Mutuma",
    created_at: new Date().toISOString(),
    items: [
      {
        product_id: 1,
        product_name: "Tea",
        quantity: 1,
        unit_price: "120.00",
        line_total: "120.00",
      },
    ],
  };

  it("needs a reason, then marks the receipt voided", async () => {
    const spy = mockApi(
      {
        "GET /api/sales/": [200, page([sale])],
        "POST /api/sales/5/void": [
          200,
          { ...sale, status: "voided", void_reason: "Rang up twice" },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/sales", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "S-0005" }));
    await user.click(screen.getByRole("button", { name: "Void sale" }));
    await user.click(screen.getByRole("button", { name: "Void" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Say why the sale is voided.");
    await user.type(screen.getByLabelText(/Why void S-0005/), "Rang up twice");
    await user.click(screen.getByRole("button", { name: "Void" }));

    expect(await screen.findByText("VOIDED: Rang up twice")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/sales/5/void")).toEqual({ reason: "Rang up twice" });
  });

  it("is not offered to a Sales Attendant", async () => {
    mockApi({ "GET /api/sales/": [200, page([sale])] }, "sales");
    const user = userEvent.setup();
    renderAt("/sales", { as: "sales" });

    await user.click(await screen.findByRole("button", { name: "S-0005" }));

    expect(screen.queryByRole("button", { name: "Void sale" })).toBeNull();
  });
});

describe("repairs (US-38)", () => {
  it("are rejected with a reason from the board", async () => {
    const repair = {
      id: 2,
      reference: "REP-002",
      asset_code: "AST-0004",
      asset_name: "Laptop",
      reporter_name: "Vincent Mutuma",
      description: "Sticker peeling",
      urgency: "low",
      status: "submitted",
      created_at: "2026-11-10T09:00:00Z",
    };
    const spy = mockApi(
      {
        "GET /api/repairs/": [200, page([repair])],
        "PUT /api/repairs/2/status": [
          200,
          { ...repair, status: "rejected", resolution: "Cosmetic only" },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/repairs", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Reject: REP-002" }));
    const dialog = screen.getByRole("dialog", { name: "Reject REP-002" });
    await user.click(within(dialog).getByRole("button", { name: "Reject repair" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Say why it is rejected.");
    await user.type(within(dialog).getByLabelText("Why it is rejected"), "Cosmetic only");
    await user.click(within(dialog).getByRole("button", { name: "Reject repair" }));

    expect(await screen.findByText(/REP-002 rejected/)).toBeInTheDocument();
    expect(bodyOf(spy, "PUT", "/api/repairs/2/status")).toEqual({
      status: "rejected",
      resolution: "Cosmetic only",
      cost: null,
    });
  });
});

describe("users (US-06)", () => {
  it("can be deactivated by the Administrator", async () => {
    const person = {
      id: 2,
      full_name: "Barclay Koin",
      email: "b@test.com",
      role: "employee",
      is_active: true,
    };
    const spy = mockApi(
      {
        "GET /api/users/": [200, page([person])],
        "POST /api/users/2/deactivate": [200, { ...person, is_active: false }],
      },
      "admin",
    );
    const confirm = globalThis.confirm;
    globalThis.confirm = () => true;
    const user = userEvent.setup();
    renderAt("/users", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "Deactivate Barclay Koin" }));

    expect(await screen.findByText("Barclay Koin is deactivated.")).toBeInTheDocument();
    expect(spy.mock.calls.some(([url]) => url.endsWith("/api/users/2/deactivate"))).toBe(true);
    globalThis.confirm = confirm;
  });
});
