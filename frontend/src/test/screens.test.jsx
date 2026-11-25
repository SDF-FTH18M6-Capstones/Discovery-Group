import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const bodyOf = (spy, method, path) => {
  const call = spy.mock.calls.find(
    ([url, options]) => options?.method === method && new URL(url).pathname === path,
  );
  return call && JSON.parse(call[1].body);
};
const called = (spy, method, path) =>
  spy.mock.calls.some(
    ([url, options]) => (options?.method || "GET") === method && new URL(url).pathname === path,
  );

const tea = {
  id: 1,
  sku: "SP-001",
  name: "Tea",
  category_name: "Beverages",
  cost_price: "80.00",
  selling_price: "120.00",
  quantity: 2,
  reorder_level: 5,
  is_low_stock: true,
};
const water = { ...tea, id: 2, sku: "SP-002", name: "Water", selling_price: "50.00", quantity: 30 };

describe("menu", () => {
  it("gives a Sales Attendant the till and their sales, but not stock or reports", async () => {
    mockApi({}, "sales");
    renderAt("/", { as: "sales" });

    const nav = await screen.findByRole("navigation", { name: "Main" });
    for (const name of ["New sale", "Sales", "Repairs", "Settings"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    for (const name of ["Stock ledger", "Purchases", "Reports", "Users"]) {
      expect(within(nav).queryByRole("link", { name })).toBeNull();
    }
  });

  it("gives the Administrator every new section", async () => {
    mockApi({}, "admin");
    renderAt("/", { as: "admin" });

    const nav = await screen.findByRole("navigation", { name: "Main" });
    for (const name of ["New sale", "Sales", "Stock ledger", "Purchases", "Repairs", "Reports"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it("keeps the till closed to an employee who types its address", async () => {
    mockApi({}, "employee");
    renderAt("/sales/new", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });
});

describe("notification bell", () => {
  it("shows the unread count on the bell", async () => {
    mockApi(
      {
        "GET /api/notifications/": (options, url) =>
          url.searchParams.get("unread") === "true" ? [200, { ...page([]), count: 3 }] : [500, {}],
      },
      "employee",
    );
    renderAt("/", { as: "employee" });

    expect(
      await screen.findByRole("link", { name: "Notifications, 3 unread" }),
    ).toBeInTheDocument();
  });
});

describe("dashboard", () => {
  it("shows the Administrator the week's sales and today's counts", async () => {
    mockApi(
      {
        "GET /api/reports/summary": [
          200,
          {
            sales_total: "4520.00",
            sales_count: 8,
            estimated_profit: "1210.00",
            by_day: [{ day: "2026-11-10", total: "4520.00", count: 8 }],
          },
        ],
        "GET /api/dashboard/pulse": [
          200,
          {
            role: "admin",
            tiles: [
              {
                key: "low_stock",
                label: "Low stock",
                count: 3,
                link: "/products?low_stock=1",
                tone: "warn",
              },
              {
                key: "approvals",
                label: "Pending approvals",
                count: 2,
                link: "/approvals",
                tone: "warn",
              },
              {
                key: "awaiting_receipt",
                label: "Orders awaiting receipt",
                count: 1,
                link: "/purchases?status=awaiting",
                tone: "warn",
              },
              {
                key: "open_repairs",
                label: "Open repairs",
                count: 0,
                link: "/repairs?status=open",
                tone: "ok",
              },
              {
                key: "sales_today",
                label: "Sales today",
                count: 4,
                amount: "980.00",
                link: "/sales?day=2026-11-23",
                tone: "ok",
              },
            ],
          },
        ],
      },
      "admin",
    );
    renderAt("/", { as: "admin" });

    expect(await screen.findByTestId("week-sales")).toHaveTextContent("KES 4,520.00");
    await waitFor(() =>
      expect(screen.getByTestId("count-sales_today")).toHaveTextContent("980.00"),
    );
    expect(screen.getByText("4 sales")).toBeInTheDocument();
    expect(screen.getByTestId("count-awaiting_receipt")).toHaveTextContent("1");
    expect(screen.getByTestId("count-open_repairs")).toHaveTextContent("0");
  });
});

describe("point of sale", () => {
  it("adds products, stops at the stock left, and sends only ids and quantities", async () => {
    const spy = mockApi(
      {
        "GET /api/products/": [200, page([tea, water])],
        "POST /api/sales/": [
          201,
          {
            id: 9,
            receipt_number: "S-0009",
            payment_method: "mpesa",
            total: "290.00",
            vat_rate: "16.00",
            vat_amount: "40.00",
            net_amount: "250.00",
            attendant_name: "Test sales",
            created_at: "2026-11-10T09:00:00Z",
            items: [
              {
                product_id: 1,
                product_name: "Tea",
                quantity: 2,
                unit_price: "120.00",
                line_total: "240.00",
              },
              {
                product_id: 2,
                product_name: "Water",
                quantity: 1,
                unit_price: "50.00",
                line_total: "50.00",
              },
            ],
          },
        ],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await user.click(await screen.findByRole("button", { name: "Add Tea" }));
    await user.click(screen.getByRole("button", { name: "One more Tea" }));
    await user.click(screen.getByRole("button", { name: "One more Tea" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Only 2 Tea in stock.");
    expect(screen.getByTestId("qty-1")).toHaveTextContent("2");

    await user.click(screen.getByRole("button", { name: "Add Water" }));
    expect(screen.getByTestId("cart-total")).toHaveTextContent("KES 290.00");
    await user.click(screen.getByText("M-Pesa"));
    await user.click(screen.getByRole("button", { name: "Complete sale" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Sale S-0009 saved");
    expect(screen.getByTestId("receipt-total")).toHaveTextContent("KES 290.00");
    expect(screen.getByTestId("receipt-vat")).toHaveTextContent("KES 40.00");
    const body = bodyOf(spy, "POST", "/api/sales/");
    expect(body).toEqual({
      payment_method: "mpesa",
      items: [
        { product_id: 1, quantity: 2 },
        { product_id: 2, quantity: 1 },
      ],
      idempotency_key: expect.any(String),
    });
    expect(body.idempotency_key.length).toBeGreaterThanOrEqual(8);
  });

  it("shows the server's message when stock ran out meanwhile", async () => {
    mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "POST /api/sales/": [
          409,
          { error: { code: 409, message: "Not enough stock: Tea (0 left)." } },
        ],
      },
      "sales",
    );
    const user = userEvent.setup();
    renderAt("/sales/new", { as: "sales" });

    await user.click(await screen.findByRole("button", { name: "Add Tea" }));
    await user.click(screen.getByRole("button", { name: "Complete sale" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Not enough stock: Tea (0 left).");
    expect(screen.getByTestId("qty-1")).toHaveTextContent("1");
  });
});

describe("sales history", () => {
  it("opens a receipt", async () => {
    mockApi(
      {
        "GET /api/sales/": [
          200,
          page([
            {
              id: 3,
              receipt_number: "S-0003",
              payment_method: "cash",
              total: "120.00",
              attendant_name: "Vincent Mutuma",
              created_at: "2026-11-10T09:00:00Z",
              items: [
                {
                  product_id: 1,
                  product_name: "Tea",
                  quantity: 1,
                  unit_price: "120.00",
                  line_total: "120.00",
                },
              ],
            },
          ]),
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/sales", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "S-0003" }));

    const receipt = screen.getByRole("article", { name: "Receipt S-0003" });
    expect(within(receipt).getByText(/Served by Vincent Mutuma/)).toBeInTheDocument();
    expect(within(receipt).getByRole("button", { name: "Print" })).toBeInTheDocument();
  });
});

const order = {
  id: 4,
  reference: "PO-0004",
  supplier_name: "Metro Wholesale",
  creator_name: "Carlos Muchemi",
  status: "ordered",
  total: "400.00",
  created_at: "2026-11-09T09:00:00Z",
  items: [
    {
      id: 11,
      product_id: 1,
      product_name: "Tea",
      quantity: 5,
      received_quantity: 0,
      outstanding: 5,
      unit_cost: "80.00",
    },
  ],
  receipts: [],
};

describe("purchases", () => {
  it("let Procurement place an order with the product's cost filled in", async () => {
    const spy = mockApi(
      {
        "GET /api/suppliers/": [200, page([{ id: 5, name: "Metro Wholesale" }])],
        "GET /api/products/": [200, page([tea])],
        "POST /api/purchases/": [201, order],
      },
      "procurement",
    );
    const user = userEvent.setup();
    renderAt("/purchases", { as: "procurement" });

    await user.click(await screen.findByRole("button", { name: "New purchase order" }));
    await user.click(screen.getByRole("button", { name: "Place order" }));
    expect(screen.getByText("Choose a supplier.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Supplier"), "Met");
    await user.click(await screen.findByRole("option", { name: /Metro Wholesale/ }));
    await user.type(screen.getByLabelText("Product 1"), "Tea");
    await user.click(await screen.findByRole("option", { name: /Tea/ }));
    expect(screen.getByLabelText("Unit cost 1")).toHaveValue(80);
    await user.clear(screen.getByLabelText("Qty 1"));
    await user.type(screen.getByLabelText("Qty 1"), "5");
    await user.click(screen.getByRole("button", { name: "Place order" }));

    expect(await screen.findByText("PO-0004 placed with Metro Wholesale.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/purchases/")).toEqual({
      supplier_id: 5,
      request_id: null,
      notes: null,
      confirm: true,
      items: [{ product_id: 1, quantity: 5, unit_cost: "80.00" }],
    });
  });

  it("let Inventory receive part of an order, but not place or cancel one", async () => {
    const spy = mockApi(
      {
        "GET /api/purchases/": [200, page([order])],
        "POST /api/purchases/4/receive": [
          200,
          {
            ...order,
            status: "partially_received",
            receipts: [{ id: 1, reference: "GRN-0001", items: [] }],
          },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/purchases", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Receive PO-0004" }));
    const dialog = screen.getByRole("dialog", { name: "Receive PO-0004" });
    const arrived = within(dialog).getByLabelText("Tea arrived");
    expect(arrived).toHaveValue(5);
    await user.clear(arrived);
    await user.type(arrived, "9");
    await user.click(within(dialog).getByRole("button", { name: "Confirm delivery" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("only 5 still to come");
    await user.clear(arrived);
    await user.type(arrived, "3");
    await user.click(within(dialog).getByRole("button", { name: "Confirm delivery" }));

    expect(await screen.findByText(/GRN-0001 recorded for PO-0004/)).toBeInTheDocument();
    const body = bodyOf(spy, "POST", "/api/purchases/4/receive");
    expect(body.lines).toEqual([{ item_id: 11, quantity: 3 }]);
    expect(body.idempotency_key).toEqual(expect.any(String));
    expect(screen.queryByRole("button", { name: "New purchase order" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel PO-0004" })).toBeNull();
  });
});

describe("stock ledger", () => {
  it("checks an adjustment, then sends it", async () => {
    const spy = mockApi(
      {
        "GET /api/products/": [200, page([tea])],
        "GET /api/stock/movements": [
          200,
          page([
            {
              id: 1,
              product_id: 1,
              product_name: "Tea",
              change: -1,
              type: "sale",
              reason: "Point of sale",
              user_name: "Vincent Mutuma",
              created_at: "2026-11-10T09:00:00Z",
            },
          ]),
        ],
        "POST /api/stock/adjustments": [
          201,
          { id: 2, product_name: "Tea", change: -1, balance_now: 1 },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/stock", { as: "inventory" });

    expect(await screen.findByText("Point of sale")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Adjust stock" }));
    await user.click(screen.getByRole("button", { name: "Save adjustment" }));
    expect(screen.getByText("Choose a product.")).toBeInTheDocument();
    expect(screen.getByText("Enter a whole number, not 0 (minus to remove).")).toBeInTheDocument();

    const form = screen.getByRole("form", { name: "Adjust stock" });
    await user.type(within(form).getByLabelText("Product"), "Tea");
    await user.click(await screen.findByRole("option", { name: /Tea/ }));
    await user.type(screen.getByLabelText("Change"), "-1");
    await user.type(screen.getByLabelText("Reason"), "Damaged in store");
    await user.click(screen.getByRole("button", { name: "Save adjustment" }));

    expect(await screen.findByText("Tea: -1. Now 1 in stock.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/stock/adjustments")).toEqual({
      product_id: 1,
      change: -1,
      reason: "Damaged in store",
    });
  });
});

describe("product detail", () => {
  it("shows the stock trace to an Inventory Manager", async () => {
    mockApi(
      {
        "GET /api/products/1": [200, tea],
        "GET /api/products/1/timeline": [
          200,
          page([
            {
              at: "2026-11-10T09:00:00Z",
              action: "Received",
              summary: "PO-0001 received",
              change: "+10 (now 12)",
              reference: "GRN-0001",
              user_name: "Keith Gachuche",
            },
            {
              at: "2026-11-09T09:00:00Z",
              action: "Updated",
              summary: "Tea edited",
              change: "Selling price 100.00 → 120.00",
              reference: null,
              user_name: "Keith Gachuche",
            },
          ]),
        ],
      },
      "inventory",
    );
    renderAt("/products/1", { as: "inventory" });

    expect(await screen.findByRole("heading", { name: "Tea" })).toBeInTheDocument();
    expect(await screen.findByText("PO-0001 received")).toBeInTheDocument();
    expect(screen.getByText("+10 (now 12)")).toBeInTheDocument();
    expect(screen.getByText("Selling price 100.00 → 120.00")).toBeInTheDocument();
    expect(screen.getByText("Low stock")).toBeInTheDocument();
  });

  it("hides the trace from an employee", async () => {
    const spy = mockApi({ "GET /api/products/1": [200, tea] }, "employee");
    renderAt("/products/1", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Tea" })).toBeInTheDocument();
    expect(screen.queryByText("Trace timeline")).toBeNull();
    expect(called(spy, "GET", "/api/products/1/timeline")).toBe(false);
  });
});

const repair = {
  id: 2,
  reference: "REP-002",
  asset_code: "AST-0004",
  asset_name: "Laptop",
  reporter_name: "Vincent Mutuma",
  description: "Screen flickers",
  status: "submitted",
  created_at: "2026-11-10T09:00:00Z",
};

describe("repairs", () => {
  it("let an employee report a fault on an asset they hold", async () => {
    const spy = mockApi(
      {
        "GET /api/assets/": [200, page([{ id: 4, asset_code: "AST-0004", name: "Laptop" }])],
        "POST /api/repairs/": [201, repair],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/repairs", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "Report a fault" }));
    await user.selectOptions(
      screen.getByLabelText("Asset"),
      await screen.findByRole("option", { name: "AST-0004 · Laptop" }),
    );
    await user.type(screen.getByLabelText("What is wrong?"), "Screen flickers");
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(await screen.findByText(/REP-002 sent/)).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/repairs/")).toEqual({
      asset_id: 4,
      description: "Screen flickers",
      urgency: "normal",
    });
  });

  it("move along the board at once, and back if the server refuses", async () => {
    mockApi(
      {
        "GET /api/repairs/": [200, page([repair])],
        "PUT /api/repairs/2/status": [
          409,
          { error: { code: 409, message: "This repair is already in progress." } },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/repairs", { as: "inventory" });

    const submitted = await screen.findByRole("region", { name: "Submitted" });
    await within(submitted).findByText("Laptop");
    await user.click(screen.getByRole("button", { name: "Start repair: REP-002" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This repair is already in progress.",
    );
    expect(
      within(screen.getByRole("region", { name: "Submitted" })).getByText("Laptop"),
    ).toBeInTheDocument();
  });
});

describe("notifications", () => {
  const note = {
    id: 1,
    message: "Tea is low on stock (2 left).",
    is_read: false,
    created_at: "2026-11-10T09:00:00Z",
  };

  it("are marked read straight away", async () => {
    const spy = mockApi(
      {
        "GET /api/notifications/": [200, page([note])],
        "POST /api/notifications/1/read": [200, { ...note, is_read: true }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/notifications", { as: "inventory" });

    await user.click(
      await screen.findByRole("button", { name: "Mark read: Tea is low on stock (2 left)." }),
    );

    expect(screen.queryByRole("button", { name: /Mark read:/ })).toBeNull();
    await waitFor(() => expect(called(spy, "POST", "/api/notifications/1/read")).toBe(true));
  });

  it("come back as unread if the server refuses", async () => {
    mockApi(
      {
        "GET /api/notifications/": [200, page([note])],
        "POST /api/notifications/read-all": [500, { error: { message: "Server error" } }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/notifications", { as: "inventory" });

    await screen.findByText("Tea is low on stock (2 left).");
    await user.click(screen.getByRole("button", { name: "Mark all as read" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
    expect(screen.getByRole("button", { name: /Mark read:/ })).toBeInTheDocument();
  });
});

describe("reports", () => {
  it("show the Administrator the period's figures", async () => {
    const spy = mockApi(
      {
        "GET /api/reports/summary": [
          200,
          {
            days: 30,
            date_from: "2026-10-12",
            date_to: "2026-11-10",
            sales_total: "4520.00",
            sales_count: 8,
            average_sale: "565.00",
            estimated_profit: "1210.00",
            gross_profit: "1210.00",
            expenses_total: "400.00",
            net_profit: "810.00",
            vat_total: "623.45",
            voided_count: 1,
            by_payment: [{ key: "cash", label: "Cash", total: "4520.00", count: 8 }],
            by_attendant: [],
            purchases_received_total: "3000.00",
            stock_value: "25000.00",
            by_day: [{ day: "2026-11-10", total: "4520.00", count: 8 }],
            top_products: [{ product_id: 1, name: "Tea", quantity: 12, total: "1440.00" }],
            low_stock: [{ id: 3, name: "Sugar", quantity: 0, reorder_level: 20 }],
          },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/reports", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "30 days" }));

    expect(await screen.findByTestId("kpi-Sales")).toHaveTextContent("KES 4,520.00");
    expect(screen.getByTestId("kpi-Gross profit")).toHaveTextContent("KES 1,210.00");
    expect(screen.getByTestId("kpi-Net profit")).toHaveTextContent("KES 810.00");
    expect(screen.getByRole("link", { name: "Sugar" })).toBeInTheDocument();
    const days = spy.mock.calls
      .map(([url]) => new URL(url))
      .filter((url) => url.pathname === "/api/reports/summary")
      .map((url) => url.searchParams.get("days"));
    expect(days).toContain("30");
  });

  it("are closed to everyone else", async () => {
    mockApi({}, "inventory");
    renderAt("/reports", { as: "inventory" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });
});

describe("settings", () => {
  const business = {
    id: 1,
    name: "Test Shop",
    timezone: "Africa/Nairobi",
    currency: "KES",
    vat_rate: "16.00",
    phone: null,
    email: null,
    address: null,
    receipt_footer: null,
    join_code: "K7M2QX9P",
  };

  it("lets the Administrator invite staff and change the VAT rate", async () => {
    const spy = mockApi(
      {
        "GET /api/business": [200, business],
        "PUT /api/business": [200, { ...business, vat_rate: "8.00" }],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "admin" });

    expect(await screen.findByTestId("join-code")).toHaveTextContent("K7M2QX9P");
    const vat = screen.getByLabelText("VAT included in prices (%)");
    await user.clear(vat);
    await user.type(vat, "8");
    await user.click(screen.getByRole("button", { name: "Save business settings" }));

    expect(await screen.findByText("Business settings saved.")).toBeInTheDocument();
    expect(bodyOf(spy, "PUT", "/api/business")).toMatchObject({ name: "Test Shop", vat_rate: "8" });
  });

  it("shows other staff the business, but not the join code", async () => {
    mockApi({ "GET /api/business": [200, { ...business, join_code: null }] }, "sales");
    renderAt("/settings", { as: "sales" });

    expect(await screen.findByRole("heading", { name: "Test Shop" })).toBeInTheDocument();
    expect(screen.queryByTestId("join-code")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save business settings" })).toBeNull();
  });

  it("saves a new name and shows it in the menu", async () => {
    const spy = mockApi(
      {
        "PUT /api/auth/me": [
          200,
          { id: 1, full_name: "David Nyongesa", email: "employee@test.com", role: "employee" },
        ],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "employee" });

    const name = await screen.findByLabelText("Full name");
    await user.clear(name);
    await user.type(name, "David Nyongesa");
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
    expect(bodyOf(spy, "PUT", "/api/auth/me")).toEqual({
      full_name: "David Nyongesa",
      phone: null,
    });
    expect(screen.getAllByText("David Nyongesa").length).toBeGreaterThan(0);
  });

  it("shows the server's answer under the current password", async () => {
    mockApi(
      {
        "POST /api/auth/password": [
          422,
          {
            error: {
              code: 422,
              message: "Some fields are invalid.",
              details: { current_password: ["Your current password is not correct."] },
            },
          },
        ],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "Change password" }));
    expect(screen.getByText("Enter your current password.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Current password"), "wrong-one1");
    await user.type(screen.getByLabelText("New password"), "NewSecret123");
    await user.type(screen.getByLabelText("Confirm new password"), "NewSecret123");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("Your current password is not correct.")).toBeInTheDocument();
  });

  it("chooses the theme", async () => {
    mockApi({}, "employee");
    const user = userEvent.setup();
    renderAt("/settings", { as: "employee" });

    await user.click(await screen.findByRole("radio", { name: "Dark" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("stockpilot.theme")).toBe("dark");
  });
});
