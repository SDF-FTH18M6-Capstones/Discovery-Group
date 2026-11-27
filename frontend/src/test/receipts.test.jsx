import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "./helpers";

vi.mock("../features/receipts/readPhoto", () => ({
  shrink: vi.fn(async () => new Blob(["jpeg"], { type: "image/jpeg" })),
  readOnDevice: vi.fn(async (_image, onProgress) => {
    onProgress(50);
    return "NAIVAS SUPERMARKET LTD\nSUGAR 1KG 2 x 165.00 330.00\nTOTAL 330.00";
  }),
}));

const sugar = { id: 3, name: "Sugar 1kg", sku: "SUG-1", quantity: 10 };
const reading = {
  supplier: "NAIVAS SUPERMARKET LTD",
  supplier_id: null,
  date: "2026-11-21",
  number: "0045-778812",
  total: "1045.00",
  tax: "144.14",
  items: [
    {
      description: "SUGAR 1KG",
      quantity: "2",
      unit_price: "165.00",
      amount: "330.00",
      product_id: 3,
      product: sugar,
    },
    {
      description: "BREAD 400G",
      quantity: "3",
      unit_price: "65.00",
      amount: "195.00",
      product_id: null,
      product: null,
    },
  ],
};

const photo = () => new File(["photo"], "receipt.jpg", { type: "image/jpeg" });

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:receipt");
  URL.revokeObjectURL = vi.fn();
});

describe("receipt scanning", () => {
  it("reads on the phone and adds the matched lines to stock", async () => {
    let sentText = null;
    let sentStock = null;
    mockApi(
      {
        "GET /api/receipts/reader": [200, { mode: "device", can_expense: false, can_stock: true }],
        "POST /api/receipts/text": (options) => {
          sentText = JSON.parse(options.body).text;
          return [200, reading];
        },
        "POST /api/receipts/stock": (options) => {
          sentStock = JSON.parse(options.body);
          return [
            201,
            { purchase_id: 9, reference: "PO-0009", receipt_reference: "GR-0004", total: "330.00" },
          ];
        },
      },
      "procurement",
    );
    const user = userEvent.setup();
    renderAt("/receipts/scan", { as: "procurement" });

    expect(await screen.findByText(/read on this device and is not uploaded/)).toBeInTheDocument();
    await user.upload(screen.getByLabelText(/Take or choose a photo/), photo());

    expect(await screen.findByText("On the receipt: SUGAR 1KG")).toBeInTheDocument();
    expect(sentText).toContain("NAIVAS");
    expect(screen.queryByText("What is this receipt for?")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Add line 2 to stock")).toBeDisabled();
    expect(screen.getByText(/1 product · KES 330.00/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add to stock" }));

    expect(sentStock).toEqual({
      supplier_id: null,
      supplier_name: "NAIVAS SUPERMARKET LTD",
      number: "0045-778812",
      lines: [{ product_id: 3, quantity: 2, unit_cost: "165.00" }],
    });
    expect(await screen.findByRole("link", { name: "PO-0009" })).toHaveAttribute(
      "href",
      "/purchases?open=9",
    );
  });

  it("lets an owner choose an expense and fills it from the receipt", async () => {
    let sentExpense = null;
    mockApi(
      {
        "GET /api/receipts/reader": [200, { mode: "device", can_expense: true, can_stock: true }],
        "POST /api/receipts/text": [200, reading],
        "POST /api/expenses/": (options) => {
          sentExpense = JSON.parse(options.body);
          return [201, { id: 1 }];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/receipts/scan", { as: "admin" });

    await user.upload(await screen.findByLabelText(/Take or choose a photo/), photo());
    await user.click(await screen.findByRole("radio", { name: /An expense/ }));

    expect(screen.getByLabelText("Amount")).toHaveValue(1045);
    await user.click(screen.getByRole("button", { name: "Save expense" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give a category");

    await user.type(screen.getByLabelText("Category"), "Shop supplies");
    await user.click(screen.getByRole("button", { name: "Save expense" }));

    expect(sentExpense).toEqual({
      spent_on: "2026-11-21",
      category: "Shop supplies",
      description: "NAIVAS SUPERMARKET LTD, receipt 0045-778812",
      amount: "1045.00",
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Expense of KES 1,045.00 saved");
  });

  it("sends the photo online when that is set up and explains failures", async () => {
    let uploaded = null;
    mockApi(
      {
        "GET /api/receipts/reader": [200, { mode: "ai", can_expense: true, can_stock: false }],
        "POST /api/receipts/photo": (options) => {
          uploaded = options.body;
          return [502, { error: { message: "The receipt could not be read online just now." } }];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/receipts/scan", { as: "admin" });

    expect(await screen.findByText(/read online and are not kept/)).toBeInTheDocument();
    await user.upload(screen.getByLabelText(/Take or choose a photo/), photo());

    expect(await screen.findByRole("alert")).toHaveTextContent("could not be read online");
    expect(uploaded.get("photo").type).toBe("image/jpeg");
  });

  it("asks for a product before stocking", async () => {
    mockApi(
      {
        "GET /api/receipts/reader": [200, { mode: "device", can_expense: false, can_stock: true }],
        "POST /api/receipts/text": [200, { ...reading, items: [] }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/receipts/scan", { as: "inventory" });

    await user.upload(await screen.findByLabelText(/Take or choose a photo/), photo());
    await user.click(await screen.findByRole("button", { name: "Add to stock" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Match at least one line to a product.");
  });

  it("appears in the menu only for people who buy, stock or run the business", async () => {
    mockApi({}, "sales");
    renderAt("/", { as: "sales" });
    await screen.findByRole("navigation", { name: /main/i });
    expect(screen.queryByRole("link", { name: "Scan a receipt" })).not.toBeInTheDocument();
  });
});
