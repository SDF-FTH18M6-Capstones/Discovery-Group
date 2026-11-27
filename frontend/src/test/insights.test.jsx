import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const days = (count, start, value) =>
  Array.from({ length: count }, (_, n) => {
    const day = new Date(start);
    day.setDate(day.getDate() + n);
    return { date: day.toISOString().slice(0, 10), takings: value };
  });

const insights = {
  sales: {
    ready: true,
    days_of_history: 60,
    accuracy: 91,
    history: days(28, "2026-10-30", 1000),
    forecast: days(14, "2026-11-27", 1100).map((day) => ({
      date: day.date,
      expected: 1100,
      low: 900,
      high: 1300,
    })),
    comparisons: [
      { key: "yesterday", value: 1200, usual: 1000, change: 20 },
      { key: "week", value: 4000, usual: 5000, change: -20 },
      { key: "best_day", value: 2500, date: "2026-11-14" },
    ],
  },
  stock: {
    running_out: [
      { id: 3, name: "Sugar 1kg", quantity: 6, per_day: 1.9, days_left: 3, suggested_order: 21 },
    ],
    slow_movers: [{ id: 5, name: "Umbrella", quantity: 4, tied_up: 1200 }],
    most_profitable: [{ id: 7, name: "Bread", profit: 1740, sold: 58 }],
  },
  customers: {
    top: [
      {
        name: "JANE WANJIKU",
        phone: "0712***678",
        total: 8400,
        visits: 7,
        last_at: "2026-11-25T10:00:00Z",
      },
    ],
    gone_quiet: [
      {
        name: "PETER OTIENO",
        phone: null,
        total: 0,
        visits: 4,
        last_at: "2026-10-01T10:00:00Z",
      },
    ],
  },
  cash: {
    ready: true,
    weeks: days(8, "2026-10-05", 0).map((day) => ({ week: day.date, in: 7000, out: 6000 })),
    expected_in: 30000,
    expected_out: 34000,
    expected_net: -4000,
    balance: 5000,
    balance_at: "2026-11-26T18:00:00Z",
    projected_balance: 1000,
  },
};

const transaction = {
  id: 11,
  receipt: "QK71ZP3X12",
  occurred_at: "2026-11-20T09:15:00Z",
  direction: "out",
  amount: 2500,
  category: "other_expense",
  counterparty: "MAMA MBOGA SUPPLIES",
  phone: null,
  sale_id: null,
};

describe("insights", () => {
  it("shows the forecast, cash warning, stock and customers", async () => {
    mockApi({ "GET /api/insights": [200, insights] }, "admin");
    renderAt("/insights", { as: "admin" });

    expect(await screen.findByRole("heading", { name: "Insights" })).toBeInTheDocument();
    expect(screen.getByText(/20% above a usual day like it/)).toBeInTheDocument();
    expect(screen.getByText(/20% below the same days last week/)).toBeInTheDocument();
    expect(screen.getByText(/91% accurate/)).toBeInTheDocument();
    expect(screen.getByText(/Expect about KES 7,700.00 over the next 7 days/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/More is likely to go out/);
    expect(screen.getByText(/Order about 21 to cover two weeks/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Umbrella" })).toHaveAttribute("href", "/products/5");
    expect(screen.getByText("JANE WANJIKU")).toBeInTheDocument();
    expect(screen.getByText("PETER OTIENO")).toBeInTheDocument();
  });

  it("points to M-Pesa imports while there is too little history", async () => {
    mockApi(
      {
        "GET /api/insights": [
          200,
          {
            ...insights,
            sales: {
              ready: false,
              days_of_history: 5,
              accuracy: null,
              history: [],
              forecast: [],
              comparisons: [],
            },
            cash: { ready: false, weeks: [] },
          },
        ],
      },
      "admin",
    );
    renderAt("/insights", { as: "admin" });

    expect(await screen.findByText("Not enough history yet")).toBeInTheDocument();
    expect(screen.getByText(/StockPilot has 5 so far/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Import M-Pesa history" })).toHaveAttribute(
      "href",
      "/money",
    );
  });

  it("is only in the administrator's menu", async () => {
    mockApi({}, "sales");
    renderAt("/", { as: "sales" });
    await screen.findByRole("navigation", { name: /main/i });
    expect(screen.queryByRole("link", { name: "Insights" })).not.toBeInTheDocument();
  });
});

describe("M-Pesa money", () => {
  it("uploads a statement with its password and reports the result", async () => {
    let sent = null;
    mockApi(
      {
        "POST /api/money/statement": (options) => {
          sent = options.body;
          return [201, { id: 2, source: "statement", added: 42, duplicates: 3, skipped: 1 }];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/money", { as: "admin" });

    const file = new File(["%PDF-1.4"], "statement.pdf", { type: "application/pdf" });
    await user.upload(await screen.findByLabelText(/Statement file/), file);
    await user.type(screen.getByLabelText("Statement password"), "4321");
    await user.click(screen.getByRole("button", { name: /Read statement/ }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Added 42 transactions; 3 were already here; 1 failed or unreadable rows were skipped.",
    );
    expect(sent.get("password")).toBe("4321");
    expect(sent.get("file").name).toBe("statement.pdf");
  });

  it("asks for a file before uploading", async () => {
    mockApi({}, "admin");
    const user = userEvent.setup();
    renderAt("/money", { as: "admin" });
    await user.click(await screen.findByRole("button", { name: /Read statement/ }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose your M-Pesa statement first.");
  });

  it("reads pasted messages and shows the server's complaint", async () => {
    mockApi(
      {
        "POST /api/money/sms": [
          422,
          { error: { message: "No M-Pesa messages found in that text." } },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/money", { as: "admin" });
    await user.type(await screen.findByLabelText("Messages"), "hello");
    await user.click(screen.getByRole("button", { name: "Read messages" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No M-Pesa messages found");
  });

  it("remembers a new category and says how many earlier payments changed", async () => {
    let body = null;
    mockApi(
      {
        "GET /api/money/transactions": [200, page([transaction])],
        "PUT /api/money/transactions/11": (options) => {
          body = JSON.parse(options.body);
          return [200, { transaction: { ...transaction, category: "stock" }, also_changed: 2 }];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/money", { as: "admin" });

    const row = (await screen.findByText("MAMA MBOGA SUPPLIES")).closest("tr");
    const picker = within(row).getByLabelText("Category for QK71ZP3X12");
    expect(within(picker).queryByRole("option", { name: "Sales" })).not.toBeInTheDocument();
    await user.selectOptions(picker, "stock");

    expect(body).toEqual({ category: "stock", remember: true });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 earlier payments with MAMA MBOGA SUPPLIES changed too",
    );
  });

  it("undoes an import", async () => {
    let removed = false;
    mockApi(
      {
        "GET /api/money/imports": () => [
          200,
          page(
            removed
              ? []
              : [
                  {
                    id: 4,
                    source: "sms",
                    filename: null,
                    added: 3,
                    duplicates: 0,
                    skipped: 0,
                    created_at: "2026-11-27T08:00:00Z",
                  },
                ],
          ),
        ],
        "DELETE /api/money/imports/4": () => {
          removed = true;
          return [204, null];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/money", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: /Undo import/ }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Removed the 3 transactions from that import.",
    );
    expect(screen.queryByRole("button", { name: /Undo import/ })).not.toBeInTheDocument();
  });
});
