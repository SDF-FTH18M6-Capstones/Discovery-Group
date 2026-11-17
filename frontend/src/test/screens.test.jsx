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
        "GET /api/sales/": [200, { ...page([]), count: 4 }],
      },
      "admin",
    );
    renderAt("/", { as: "admin" });

    expect(await screen.findByTestId("week-sales")).toHaveTextContent("KES 4,520.00");
    await waitFor(() => expect(screen.getByTestId("count-sales")).toHaveTextContent("4"));
    expect(screen.getByTestId("count-orders")).toBeInTheDocument();
    expect(screen.getByTestId("count-repairs")).toBeInTheDocument();
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
    expect(bodyOf(spy, "POST", "/api/sales/")).toEqual({
      payment_method: "mpesa",
      items: [
        { product_id: 1, quantity: 2 },
        { product_id: 2, quantity: 1 },
      ],
    });
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
  items: [{ product_id: 1, product_name: "Tea", quantity: 5, unit_cost: "80.00" }],
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

    await user.selectOptions(
      screen.getByLabelText("Supplier"),
      await screen.findByRole("option", { name: "Metro Wholesale" }),
    );
    await user.selectOptions(screen.getByLabelText("Product 1"), "1");
    expect(screen.getByLabelText("Unit cost 1")).toHaveValue(80);
    await user.clear(screen.getByLabelText("Qty 1"));
    await user.type(screen.getByLabelText("Qty 1"), "5");
    await user.click(screen.getByRole("button", { name: "Place order" }));

    expect(await screen.findByText("PO-0004 placed with Metro Wholesale.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/purchases/")).toEqual({
      supplier_id: 5,
      items: [{ product_id: 1, quantity: 5, unit_cost: "80.00" }],
    });
  });

  it("let Inventory receive an order but not place or cancel one", async () => {
    const spy = mockApi(
      {
        "GET /api/purchases/": [200, page([order])],
        "POST /api/purchases/4/receive": [200, { ...order, status: "received" }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/purchases", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Receive PO-0004" }));

    expect(await screen.findByText("PO-0004 received. Stock updated.")).toBeInTheDocument();
    expect(called(spy, "POST", "/api/purchases/4/receive")).toBe(true);
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

    await user.selectOptions(screen.getByLabelText("Product"), "1");
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
        "GET /api/stock/movements": [
          200,
          page([
            {
              id: 1,
              product_id: 1,
              change: 10,
              type: "purchase",
              reason: "PO-0001 received",
              user_name: "Keith Gachuche",
              created_at: "2026-11-10T09:00:00Z",
            },
          ]),
        ],
      },
      "inventory",
    );
    renderAt("/products/1", { as: "inventory" });

    expect(await screen.findByRole("heading", { name: "Tea" })).toBeInTheDocument();
    expect(await screen.findByText("PO-0001 received")).toBeInTheDocument();
    expect(screen.getByText("Low stock")).toBeInTheDocument();
  });

  it("hides the trace from an employee", async () => {
    const spy = mockApi({ "GET /api/products/1": [200, tea] }, "employee");
    renderAt("/products/1", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Tea" })).toBeInTheDocument();
    expect(screen.queryByText("Stock trace")).toBeNull();
    expect(called(spy, "GET", "/api/stock/movements")).toBe(false);
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
    expect(screen.getByTestId("kpi-Estimated profit")).toHaveTextContent("KES 1,210.00");
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
    expect(bodyOf(spy, "PUT", "/api/auth/me")).toEqual({ full_name: "David Nyongesa" });
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
