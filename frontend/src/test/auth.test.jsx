import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { api } from "../api/client";
import { loadSession, saveSession } from "../auth/session";
import { mockApi, page, renderAt, userFor } from "./helpers";

describe("protected pages", () => {
  it("send a signed-out visitor to the sign-in page", async () => {
    mockApi();
    renderAt("/products");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Products" })).toBeNull();
  });

  it("let a signed-in user in", async () => {
    mockApi({}, "employee");
    renderAt("/products", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "Products" })).toBeInTheDocument();
  });

  it("show 'No access' when the role is not allowed", async () => {
    mockApi({}, "employee");
    renderAt("/suppliers", { as: "employee" });

    expect(await screen.findByRole("heading", { name: "No access" })).toBeInTheDocument();
  });

  it("hide links and buttons the role cannot use", async () => {
    mockApi(
      { "GET /api/products/": [200, page([{ id: 1, name: "Tea", sku: "SP-1", quantity: 5 }])] },
      "employee",
    );
    renderAt("/products", { as: "employee" });

    expect(await screen.findByText("Tea")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Suppliers" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add product" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });
});

describe("sign in", () => {
  it("takes email and password, then opens the page asked for", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/login": [
        200,
        { access_token: "new-access", refresh_token: "new-refresh", user: userFor("inventory") },
      ],
      "GET /api/auth/me": [200, userFor("inventory")],
    });
    const user = userEvent.setup();
    renderAt("/products");

    await user.type(await screen.findByLabelText("Email"), "inventory@test.com");
    await user.type(screen.getByLabelText("Password"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Products" })).toBeInTheDocument();
    expect(loadSession().accessToken).toBe("new-access");
    expect(loadSession().refreshToken).toBe("new-refresh");
    const login = fetchSpy.mock.calls.find(([url]) => url.endsWith("/api/auth/login"));
    expect(JSON.parse(login[1].body)).toEqual({
      email: "inventory@test.com",
      password: "Secret123!",
    });
  });

  it("shows the server's message when the password is wrong", async () => {
    mockApi({
      "POST /api/auth/login": [
        401,
        { error: { code: 401, message: "Email or password is incorrect." } },
      ],
    });
    const user = userEvent.setup();
    renderAt("/login");

    await user.type(screen.getByLabelText("Email"), "someone@test.com");
    await user.type(screen.getByLabelText("Password"), "Wrong123!");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(loadSession()).toBeNull();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("checks the fields before calling the server", async () => {
    const fetchSpy = mockApi();
    const user = userEvent.setup();
    renderAt("/login");

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => url.endsWith("/api/auth/login"))).toBe(false);
  });

  it("signs out on the server too, and clears the stored session", async () => {
    const fetchSpy = mockApi(
      { "POST /api/auth/logout": [200, { message: "Signed out." }] },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/products", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(loadSession()).toBeNull();
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/api/auth/logout"));
    expect(call[1].headers.Authorization).toBe("Bearer test-access");
  });

  it("sends a password reset link and always gives the same answer", async () => {
    const answer = "If that email has an account, we sent a link to reset the password.";
    const fetchSpy = mockApi({ "POST /api/auth/forgot-password": [200, { message: answer }] });
    const user = userEvent.setup();
    renderAt("/login");

    await user.click(screen.getByRole("link", { name: "Forgot your password?" }));
    await user.type(screen.getByLabelText("Email"), "barclay@test.com");
    await user.click(screen.getByRole("button", { name: "Send the link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(answer);
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/forgot-password"));
    expect(JSON.parse(call[1].body)).toEqual({ email: "barclay@test.com" });
  });

  it("sets a new password from the emailed link", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/reset-password": [200, { message: "Password changed. You can now sign in." }],
    });
    const user = userEvent.setup();
    renderAt("/reset-password?token=abc123def456");

    await user.type(screen.getByLabelText("New password"), "Brand9New");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand9New");
    await user.click(screen.getByRole("button", { name: "Save new password" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Password changed.");
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/reset-password"));
    expect(JSON.parse(call[1].body)).toEqual({ token: "abc123def456", password: "Brand9New" });
  });
});

describe("sign up", () => {
  it("checks every field before sending", async () => {
    const fetchSpy = mockApi();
    const user = userEvent.setup();
    renderAt("/register");

    await user.type(screen.getByLabelText("Password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "different");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Enter your full name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email.")).toBeInTheDocument();
    expect(
      screen.getByText("Use at least 8 characters with letters and numbers."),
    ).toBeInTheDocument();
    expect(screen.getByText("The passwords do not match.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => url.endsWith("/api/auth/register"))).toBe(false);
  });

  it("creates the account and goes to sign in with the email filled in", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/register": [201, { message: "Account created. You can now sign in." }],
    });
    const user = userEvent.setup();
    renderAt("/register?code=demo2026");

    expect(screen.getByLabelText("Join code")).toHaveValue("DEMO2026");
    await user.type(screen.getByLabelText("Full name"), "Barclay Koin");
    await user.type(screen.getByLabelText("Email"), "barclay@test.com");
    await user.type(screen.getByLabelText("Password"), "Secret123!");
    await user.type(screen.getByLabelText("Confirm password"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Account created. You can now sign in.");
    expect(screen.getByLabelText("Email")).toHaveValue("barclay@test.com");
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/api/auth/register"));
    expect(JSON.parse(call[1].body)).toEqual({
      full_name: "Barclay Koin",
      email: "barclay@test.com",
      password: "Secret123!",
      join_code: "DEMO2026",
    });
  });

  it("starts a new business and signs its owner in as Administrator", async () => {
    const owner = { ...userFor("admin"), business: { id: 9, name: "Mama Mboga", currency: "KES" } };
    const fetchSpy = mockApi({
      "POST /api/auth/register-business": [
        201,
        { access_token: "a", refresh_token: "r", user: owner },
      ],
      "GET /api/auth/me": [200, owner],
      "GET /api/dashboard/pulse": [200, { role: "admin", tiles: [] }],
    });
    const user = userEvent.setup();
    renderAt("/register");

    await user.click(screen.getByRole("button", { name: "New business" }));
    await user.type(screen.getByLabelText("Business name"), "Mama Mboga");
    await user.type(screen.getByLabelText("Full name"), "Wanjiku Kamau");
    await user.type(screen.getByLabelText("Your work email"), "w@mboga.test");
    await user.type(screen.getByLabelText("Password"), "Secret123!");
    await user.type(screen.getByLabelText("Confirm password"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "Create business" }));

    expect(await screen.findByText("Your business is ready")).toBeInTheDocument();
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/register-business"));
    expect(JSON.parse(call[1].body)).toEqual({
      business_name: "Mama Mboga",
      full_name: "Wanjiku Kamau",
      email: "w@mboga.test",
      password: "Secret123!",
    });
  });

  it("shows the server's message when the email is taken", async () => {
    mockApi({
      "POST /api/auth/register": [
        409,
        { error: { code: 409, message: "An account with this email already exists." } },
      ],
    });
    const user = userEvent.setup();
    renderAt("/register");

    await user.type(screen.getByLabelText("Join code"), "DEMO2026");
    await user.type(screen.getByLabelText("Full name"), "Barclay Koin");
    await user.type(screen.getByLabelText("Email"), "barclay@test.com");
    await user.type(screen.getByLabelText("Password"), "Secret123!");
    await user.type(screen.getByLabelText("Confirm password"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An account with this email already exists.",
    );
  });
});

describe("the fetch interceptor", () => {
  it("sends the access token on every request", async () => {
    saveSession({ accessToken: "abc", refreshToken: "r", user: userFor("admin") });
    const fetchSpy = mockApi({ "GET /api/products/": [200, page([])] });

    await api("/api/products/");

    expect(fetchSpy.mock.calls[0][1].headers.Authorization).toBe("Bearer abc");
  });

  it("renews an expired token once and retries the request", async () => {
    saveSession({ accessToken: "old", refreshToken: "refresh", user: userFor("admin") });
    const fetchSpy = mockApi({
      "GET /api/products/": (options) =>
        options.headers.Authorization === "Bearer fresh"
          ? [200, page([{ id: 1 }])]
          : [401, { error: { code: 401, message: "Your session has expired." } }],
      "POST /api/auth/refresh": [200, { access_token: "fresh" }],
    });

    const data = await api("/api/products/");

    expect(data.count).toBe(1);
    expect(loadSession().accessToken).toBe("fresh");
    const refresh = fetchSpy.mock.calls.find(([url]) => url.endsWith("/api/auth/refresh"));
    expect(refresh[1].headers.Authorization).toBe("Bearer refresh");
  });

  it("sends the user to sign in when the refresh token has expired too", async () => {
    mockApi({
      "GET /api/products/": [401, { error: { code: 401, message: "Expired" } }],
      "POST /api/auth/refresh": [401, { error: { code: 401, message: "Expired" } }],
      "GET /api/auth/me": [401, { error: { code: 401, message: "Expired" } }],
    });
    renderAt("/products", { as: "admin" });

    expect(
      await screen.findByText("Your session has expired. Please sign in again."),
    ).toBeInTheDocument();
    await waitFor(() => expect(loadSession()).toBeNull());
  });
});
