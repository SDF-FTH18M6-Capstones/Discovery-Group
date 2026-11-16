import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const water = {
  id: 1,
  sku: "SP-001",
  name: "Water Bottle 1L",
  category_id: 1,
  category_name: "Beverages",
  cost_price: "180.00",
  selling_price: "250.00",
  quantity: 120,
  reorder_level: 20,
  is_low_stock: false,
};

describe("products page", () => {
  it("lists products from the API", async () => {
    mockApi({ "GET /api/products/": [200, page([water])] }, "admin");
    renderAt("/products", { as: "admin" });

    expect(await screen.findByText("Water Bottle 1L")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 1 · 1 total")).toBeInTheDocument();
  });

  it("shows field errors before sending an empty form", async () => {
    const fetchSpy = mockApi({}, "admin");
    const user = userEvent.setup();
    renderAt("/products", { as: "admin" });

    await user.click(screen.getByRole("button", { name: "Add product" }));
    await user.click(screen.getByRole("button", { name: "Save product" }));

    expect(screen.getByText("SKU is required.")).toBeInTheDocument();
    expect(screen.getByText("Choose a category.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  });

  it("captures what was typed and sends it to the API", async () => {
    const fetchSpy = mockApi(
      {
        "GET /api/categories/": [200, page([{ id: 1, name: "Beverages" }])],
        "POST /api/products/": [201, water],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/products", { as: "admin" });

    await user.click(screen.getByRole("button", { name: "Add product" }));
    await user.type(screen.getByLabelText("SKU"), "SP-001");
    await user.type(screen.getByLabelText("Name"), "Water Bottle 1L");
    await user.selectOptions(await screen.findByLabelText("Category"), "1");
    await user.type(screen.getByLabelText("Cost price (KES)"), "180");
    await user.type(screen.getByLabelText("Selling price (KES)"), "250");
    await user.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => {
      const post = fetchSpy.mock.calls.find(([, options]) => options?.method === "POST");
      expect(JSON.parse(post[1].body)).toMatchObject({
        sku: "SP-001",
        name: "Water Bottle 1L",
        category_id: 1,
        cost_price: "180",
        selling_price: "250",
        quantity: 0,
      });
    });
    await waitFor(() => expect(screen.queryByRole("form", { name: "Add product" })).toBeNull());
  });

  it("shows the server's error next to the field", async () => {
    mockApi(
      {
        "GET /api/categories/": [200, page([{ id: 1, name: "Beverages" }])],
        "POST /api/products/": [
          409,
          { error: { code: 409, message: "SKU 'SP-001' is already used" } },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/products", { as: "admin" });

    await user.click(screen.getByRole("button", { name: "Add product" }));
    await user.type(screen.getByLabelText("SKU"), "SP-001");
    await user.type(screen.getByLabelText("Name"), "Copy");
    await user.selectOptions(await screen.findByLabelText("Category"), "1");
    await user.type(screen.getByLabelText("Cost price (KES)"), "1");
    await user.type(screen.getByLabelText("Selling price (KES)"), "2");
    await user.click(screen.getByRole("button", { name: "Save product" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("SKU 'SP-001' is already used");
  });
});

describe("suppliers page", () => {
  it("validates email and saves a supplier", async () => {
    const fetchSpy = mockApi({ "POST /api/suppliers/": [201, { id: 1, name: "Metro" }] }, "admin");
    const user = userEvent.setup();
    renderAt("/suppliers", { as: "admin" });

    await user.click(screen.getByRole("button", { name: "Add supplier" }));
    await user.type(screen.getByLabelText("Name"), "Metro");
    await user.type(screen.getByLabelText("Email"), "wrong");
    await user.click(screen.getByRole("button", { name: "Save supplier" }));
    expect(screen.getByText("Enter a valid email.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Email"));
    await user.type(screen.getByLabelText("Email"), "orders@metro.co.ke");
    await user.click(screen.getByRole("button", { name: "Save supplier" }));

    await waitFor(() => {
      const post = fetchSpy.mock.calls.find(([, options]) => options?.method === "POST");
      expect(JSON.parse(post[1].body)).toEqual({
        name: "Metro",
        email: "orders@metro.co.ke",
        phone: null,
      });
    });
  });
});