import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderAt } from "./helpers";

const counted = (count) => ({ ...page([]), count });
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
    expect(within(nav).getByRole("link", { name: "My assets" })).toBeInTheDocument();
    for (const hidden of ["Assets", "Approvals", "Suppliers", "Users"]) {
      expect(within(nav).queryByRole("link", { name: hidden })).toBeNull();
    }
  });
});

describe("dashboard", () => {
  it("counts an employee's own pending requests and the assets they hold", async () => {
    const spy = mockApi(
      {
        "GET /api/requests/": (options, url) =>
          url.searchParams.get("mine") === "true" ? [200, counted(2)] : [500, {}],
        "GET /api/assets/": [200, counted(1)],
        "GET /api/products/": [200, counted(3)],
      },
      "employee",
    );
    renderAt("/", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Welcome, Test" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("count-pending")).toHaveTextContent("2"));
    expect(screen.getByText("Assets you hold")).toBeInTheDocument();
    expect(screen.getByTestId("count-low")).toHaveTextContent("3");
    expect(screen.queryByText("Suppliers")).toBeNull();
    expect(urlsFor(spy, "/api/products/")[0].searchParams.get("low_stock")).toBe("true");
  });

  it("shows a Procurement Manager every pending request and the suppliers", async () => {
    const spy = mockApi({ "GET /api/requests/": [200, counted(5)] }, "procurement");
    renderAt("/", { as: "procurement" });

    await waitFor(() => expect(screen.getByTestId("count-pending")).toHaveTextContent("5"));
    expect(screen.getByText("Requests waiting for a decision")).toBeInTheDocument();
    expect(screen.getByTestId("count-suppliers")).toBeInTheDocument();
    expect(urlsFor(spy, "/api/requests/")[0].searchParams.get("mine")).toBeNull();
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
      expect(bodyOf(spy, "POST", "/api/categories/")).toEqual({ name: "Snacks" }),
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
  requester_name: "Alex Kamau",
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
    });
  });

  it("lets only pending requests be withdrawn, and shows the decision on the others", async () => {
    const decided = {
      ...pending,
      id: 8,
      item: "Standing desk",
      status: "rejected",
      reviewer_name: "Jane Otieno",
      review_comment: "Not in this quarter's budget.",
    };
    const spy = mockApi(
      {
        "GET /api/requests/": [200, page([pending, decided])],
        "DELETE /api/requests/7": [204, null],
      },
      "employee",
    );
    const user = userEvent.setup();
    renderAt("/requests", { as: "employee" });

    expect(
      await screen.findByText("Jane Otieno: “Not in this quarter's budget.”"),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Withdraw" })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByText("Request for Printer paper withdrawn.")).toBeInTheDocument();
    expect(spy.mock.calls.some(([, o]) => o?.method === "DELETE")).toBe(true);
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
  it("are 'My assets', read-only, for an employee", async () => {
    mockApi({}, "employee");
    renderAt("/assets", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "My assets" })).toBeInTheDocument();
    expect(await screen.findByText("No assets are assigned to you.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add asset" })).toBeNull();
  });

  it("need a holder when assigned, picked from the people list", async () => {
    const spy = mockApi(
      {
        "GET /api/users/choices": [200, [{ id: 2, full_name: "Alex Kamau", role: "employee" }]],
        "POST /api/assets/": [201, { id: 9 }],
      },
      "inventory",
    );
    const user = userEvent.setup();
    renderAt("/assets", { as: "inventory" });

    await user.click(await screen.findByRole("button", { name: "Add asset" }));
    await user.type(screen.getByLabelText("Asset code"), "AST-0009");
    await user.type(screen.getByLabelText("Name"), "Projector");
    await user.selectOptions(screen.getByLabelText("Status"), "assigned");
    await user.click(screen.getByRole("button", { name: "Save asset" }));
    expect(screen.getByText("Choose who holds it.")).toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText("Held by"), "2");
    await user.click(screen.getByRole("button", { name: "Save asset" }));

    await waitFor(() =>
      expect(bodyOf(spy, "POST", "/api/assets/")).toEqual({
        asset_code: "AST-0009",
        name: "Projector",
        status: "assigned",
        assigned_to: 2,
      }),
    );
  });
});

describe("users", () => {
  const people = [
    { id: 1, full_name: "Test admin", email: "admin@test.com", role: "admin" },
    { id: 2, full_name: "Alex Kamau", email: "alex@test.com", role: "employee" },
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
    await user.selectOptions(screen.getByLabelText("Role for Alex Kamau"), "sales");
    await user.click(screen.getByRole("button", { name: "Save role for Alex Kamau" }));

    expect(await screen.findByText("Alex Kamau is now Sales Attendant.")).toBeInTheDocument();
    expect(bodyOf(spy, "PUT", "/api/users/2/role")).toEqual({ role: "sales" });
  });

  it("are closed to everyone but the administrator", async () => {
    mockApi({}, "inventory");
    renderAt("/users", { as: "inventory" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });
});
