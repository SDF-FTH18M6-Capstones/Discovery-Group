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
const urlsFor = (spy, path) =>
  spy.mock.calls.map(([url]) => new URL(url)).filter((url) => url.pathname === path);

describe("menu", () => {
  it("shows an employee only what an employee can open", async () => {
    mockApi({}, "employee");
    renderAt("/", { as: "employee" });

    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Assets with me" })).toBeInTheDocument();
    for (const hidden of ["Assets", "Approvals", "Suppliers", "Users", "Audit log"]) {
      expect(within(nav).queryByRole("link", { name: hidden })).toBeNull();
    }
  });
});

describe("dashboard", () => {
  const tile = (key, label, count, link, extra = {}) => ({
    key,
    label,
    count,
    link,
    detail: null,
    amount: null,
    tone: count ? "warn" : "ok",
    ...extra,
  });

  it("shows an employee the Pulse tiles for their own requests and assets", async () => {
    const spy = mockApi(
      {
        "GET /api/dashboard/pulse": [
          200,
          {
            role: "employee",
            tiles: [
              tile("my_requests", "My active requests", 2, "/requests?tab=active", {
                detail: "1 awaiting a decision",
              }),
              tile("my_assets", "Assets with me", 1, "/assets"),
              tile("my_repairs", "My open repairs", 0, "/repairs?status=open"),
            ],
          },
        ],
      },
      "employee",
    );
    renderAt("/", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Welcome, Test" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("count-my_requests")).toHaveTextContent("2"));
    expect(screen.getByText("1 awaiting a decision")).toBeInTheDocument();
    const pulse = screen.getByRole("region", { name: "StockPilot Pulse" });
    expect(within(pulse).getByRole("link", { name: /Assets with me/ })).toHaveAttribute(
      "href",
      "/assets",
    );
    expect(urlsFor(spy, "/api/dashboard/pulse")).toHaveLength(1);
    expect(urlsFor(spy, "/api/assets/")).toHaveLength(0);
  });

  it("links each Procurement tile to its filtered queue", async () => {
    mockApi(
      {
        "GET /api/dashboard/pulse": [
          200,
          {
            role: "procurement",
            tiles: [
              tile("approvals", "Pending approvals", 5, "/approvals", { detail: "2 urgent" }),
              tile("awaiting_receipt", "Orders awaiting receipt", 1, "/purchases?status=awaiting"),
            ],
          },
        ],
      },
      "procurement",
    );
    renderAt("/", { as: "procurement" });

    await waitFor(() => expect(screen.getByTestId("count-approvals")).toHaveTextContent("5"));
    expect(screen.getByText("2 urgent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Orders awaiting receipt/ })).toHaveAttribute(
      "href",
      "/purchases?status=awaiting",
    );
  });
});

describe("categories", () => {
  it("are read-only for an employee", async () => {
    mockApi({ "GET /api/categories/": [200, page([{ id: 1, name: "Beverages" }])] }, "employee");
    renderAt("/categories", { as: "employee" });

    expect(await screen.findByText("Beverages")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add category" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rename" })).toBeNull();
  });

  it("can be added by an Inventory Manager, with the name checked first", async () => {
    const spy = mockApi({ "POST /api/categories/": [201, { id: 2, name: "Snacks" }] }, "inventory");
    const user = userEvent.setup();
    renderAt("/categories", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Add category" }));
    await user.click(screen.getByRole("button", { name: "Save category" }));
    expect(screen.getByText("Name is required.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/categories/")).toBeUndefined();

    await user.type(screen.getByLabelText("Category name"), "Snacks");
    await user.click(screen.getByRole("button", { name: "Save category" }));

    await waitFor(() =>
      expect(bodyOf(spy, "POST", "/api/categories/")).toEqual({ name: "Snacks", is_active: true }),
    );
  });

  it("keep the server's message when a category in use cannot be deleted", async () => {
    mockApi(
      {
        "GET /api/categories/": [200, page([{ id: 1, name: "Beverages" }])],
        "DELETE /api/categories/1": [
          409,
          { error: { code: 409, message: "This category is still used by products." } },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/categories", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This category is still used by products.",
    );
    expect(screen.getByText("Beverages")).toBeInTheDocument();
  });

  it("show the server's message for a duplicate name", async () => {
    mockApi(
      {
        "POST /api/categories/": [
          409,
          { error: { code: 409, message: "Category 'Beverages' already exists" } },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/categories", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "Add category" }));
    await user.type(screen.getByLabelText("Category name"), "Beverages");
    await user.click(screen.getByRole("button", { name: "Save category" }));

    expect(await screen.findByText("Category 'Beverages' already exists")).toBeInTheDocument();
  });
});

const pending = {
  id: 7,
  requester_id: 2,
  requester_name: "Barclay Koin",
  item: "Printer paper",
  quantity: 5,
  urgency: "normal",
  reason: "Monthly reports",
  status: "pending",
  created_at: "2026-11-16T08:00:00Z",
};

describe("my requests", () => {
  it("asks the API for the signed-in user's own requests", async () => {
    const spy = mockApi({}, "procurement");
    renderAt("/requests", { as: "procurement" });

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    await waitFor(() =>
      expect(urlsFor(spy, "/api/requests/")[0].searchParams.get("mine")).toBe("true"),
    );
  });

  it("checks the form before sending, then submits", async () => {
    const spy = mockApi(
      { "POST /api/requests/": [201, { ...pending, item: "Markers" }] },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "New request" }));
    await user.clear(screen.getByLabelText("Quantity"));
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(screen.getByText("Say what you need.")).toBeInTheDocument();
    expect(screen.getByText("Enter a whole number of 1 or more.")).toBeInTheDocument();
    expect(screen.getByText("Say why you need it.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/requests/")).toBeUndefined();

    await user.type(screen.getByLabelText("What do you need?"), "Markers");
    await user.type(screen.getByLabelText("Quantity"), "3");
    await user.selectOptions(screen.getByLabelText("Urgency"), "high");
    await user.type(screen.getByLabelText("Reason"), "Training on Monday");
    await user.click(screen.getByRole("button", { name: "Submit request" }));

    expect(await screen.findByText("Request for Markers submitted.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/requests/")).toEqual({
      item: "Markers",
      quantity: 3,
      urgency: "high",
      reason: "Training on Monday",
      product_id: null,
    });
  });

  it("lets only pending requests be cancelled, and shows the decision on the others", async () => {
    const decided = {
      ...pending,
      id: 8,
      item: "Standing desk",
      status: "rejected",
      reviewer_name: "Carlos Muchemi",
      review_comment: "Not in this quarter's budget.",
    };
    const spy = mockApi(
      {
        "GET /api/requests/": [200, page([pending, decided])],
        "POST /api/requests/7/cancel": [200, { ...pending, status: "cancelled" }],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    await user.click(await screen.findByRole("button", { name: "View request for Standing desk" }));
    const decidedView = screen.getByRole("dialog");
    expect(
      within(decidedView).getByText("Carlos Muchemi: “Not in this quarter's budget.”"),
    ).toBeInTheDocument();
    expect(within(decidedView).queryByRole("button", { name: "Cancel request" })).toBeNull();
    expect(within(decidedView).queryByRole("button", { name: "Edit" })).toBeNull();
    await user.click(within(decidedView).getByRole("button", { name: "Close" }));

    await user.click(screen.getByRole("button", { name: "View request for Printer paper" }));
    await user.click(screen.getByRole("button", { name: "Cancel request" }));
    await user.click(screen.getByRole("button", { name: "Yes, cancel it" }));

    expect(await screen.findByText("Request for Printer paper cancelled.")).toBeInTheDocument();
    expect(spy.mock.calls.some(([url]) => url.endsWith("/api/requests/7/cancel"))).toBe(true);
  });
});

describe("approvals", () => {
  it("are closed to employees", async () => {
    mockApi({}, "employee");
    renderAt("/approvals", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });

  it("need a reason to reject, then send it", async () => {
    const spy = mockApi(
      {
        "GET /api/requests/": [200, page([pending])],
        "POST /api/requests/7/reject": [200, { ...pending, status: "rejected" }],
      },
      "procurement",
    );
    const user = userEvent.setup();
    renderAt("/approvals", { as: "procurement" });

    await user.click(await screen.findByRole("button", { name: "Open request for Printer paper" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Say why the request is rejected.");
    expect(bodyOf(spy, "POST", "/api/requests/7/reject")).toBeUndefined();

    await user.type(screen.getByLabelText("Comment"), "Use the paper in store");
    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(await screen.findByText("Printer paper: rejected.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/requests/7/reject")).toEqual({
      comment: "Use the paper in store",
    });
  });

  it("approve without a comment", async () => {
    const spy = mockApi(
      {
        "GET /api/requests/": [200, page([pending])],
        "POST /api/requests/7/approve": [200, { ...pending, status: "approved" }],
      },
      "procurement",
    );
    const user = userEvent.setup();
    renderAt("/approvals", { as: "procurement" });

    await user.click(await screen.findByRole("button", { name: "Open request for Printer paper" }));
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Printer paper: approved.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/requests/7/approve")).toEqual({});
  });

  it("never offer a decision on your own request, or to an administrator", async () => {
    const own = { ...pending, requester_id: 1 };
    mockApi({ "GET /api/requests/": [200, page([own])] }, "procurement");
    const user = userEvent.setup();
    const { unmount } = renderAt("/approvals", { as: "procurement" });

    await user.click(await screen.findByRole("button", { name: "Open request for Printer paper" }));
    expect(screen.getByText(/another Procurement Manager decides it/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    unmount();
    localStorage.clear();

    mockApi({ "GET /api/requests/": [200, page([pending])] }, "admin");
    renderAt("/approvals", { as: "admin" });
    await user.click(await screen.findByRole("button", { name: "Open request for Printer paper" }));
    expect(
      screen.getByText("Only a Procurement Manager can approve or reject."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});

describe("assets", () => {
  it("are 'Assets with me', read-only, for an employee", async () => {
    mockApi({}, "employee");
    renderAt("/assets", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Assets with me" })).toBeInTheDocument();
    expect(await screen.findByText("Nothing assigned to you")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add asset" })).toBeNull();
  });

  it("are registered without a code (the server makes it) and can be handed out at once", async () => {
    const spy = mockApi(
      {
        "GET /api/users/choices": [200, [{ id: 2, full_name: "Barclay Koin", role: "employee" }]],
        "GET /api/asset-categories/": [200, page([{ id: 4, name: "Computers" }])],
        "POST /api/assets/": [201, { id: 9, asset_code: "AST-0009", name: "Projector" }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/assets", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Add asset" }));
    expect(screen.queryByLabelText("Asset code")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Save asset" }));
    expect(screen.getByText("Name is required.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Name"), "Projector");
    await user.selectOptions(await screen.findByLabelText("Category"), "4");
    await user.type(screen.getByLabelText("Serial number"), "EP-55");
    await user.selectOptions(await screen.findByLabelText("Hand it to (optional)"), "2");
    await user.click(screen.getByRole("button", { name: "Save asset" }));

    expect(await screen.findByText("AST-0009 Projector saved.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/assets/")).toMatchObject({
      name: "Projector",
      category_id: 4,
      serial_number: "EP-55",
      condition: "good",
      assigned_to: 2,
    });
  });

  it("are assigned with a condition and returned from the list", async () => {
    const laptop = {
      id: 3,
      asset_code: "AST-0003",
      barcode: "SP0001000003",
      name: "Laptop",
      status: "available",
      condition: "good",
    };
    const spy = mockApi(
      {
        "GET /api/assets/": [200, page([laptop])],
        "GET /api/users/choices": [200, [{ id: 2, full_name: "Barclay Koin", role: "employee" }]],
        "POST /api/assets/3/assign": [
          200,
          { ...laptop, status: "assigned", holder_name: "Barclay Koin" },
        ],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/assets", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Assign" }));
    const dialog = screen.getByRole("dialog", { name: "Assign AST-0003" });
    await user.click(within(dialog).getByRole("button", { name: "Assign" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Choose who receives it.");
    await user.selectOptions(await within(dialog).findByLabelText("Give it to"), "2");
    await user.selectOptions(within(dialog).getByLabelText("Condition at hand-over"), "fair");
    await user.click(within(dialog).getByRole("button", { name: "Assign" }));

    expect(await screen.findByText("Laptop is now with Barclay Koin.")).toBeInTheDocument();
    expect(bodyOf(spy, "POST", "/api/assets/3/assign")).toEqual({
      user_id: 2,
      condition: "fair",
      expected_return: null,
    });
  });
});

describe("users", () => {
  const people = [
    { id: 1, full_name: "Test admin", email: "admin@test.com", role: "admin" },
    { id: 2, full_name: "Barclay Koin", email: "barclay@test.com", role: "employee" },
  ];

  it("let an administrator change someone's role, but not their own", async () => {
    const spy = mockApi(
      {
        "GET /api/users/": [200, page(people)],
        "PUT /api/users/2/role": [200, { ...people[1], role: "sales" }],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/users", { as: "admin" });

    expect(await screen.findByLabelText("Role for Test admin")).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Role for Barclay Koin"), "sales");
    await user.click(screen.getByRole("button", { name: "Save role for Barclay Koin" }));

    expect(await screen.findByText("Barclay Koin is now Sales Attendant.")).toBeInTheDocument();
    expect(bodyOf(spy, "PUT", "/api/users/2/role")).toEqual({ role: "sales" });
  });

  it("are closed to everyone but the administrator", async () => {
    mockApi({}, "inventory");
    renderAt("/users", { as: "inventory" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });
});
