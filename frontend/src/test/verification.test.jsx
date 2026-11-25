import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { loadSession } from "../auth/session";
import { mockApi, page, renderAt, userFor } from "./helpers";

const challenge = {
  code_required: true,
  challenge_id: "abc123",
  email_hint: "i••••••••@test.com",
  expires_in: 300,
  resend_after: 0,
};

async function signInWithPassword(user) {
  await user.type(await screen.findByLabelText("Email"), "inventory@test.com");
  await user.type(screen.getByLabelText("Password"), "Secret123!");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("sign-in code (US-03)", () => {
  it("asks for the emailed code, then signs in", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/login": [200, challenge],
      "POST /api/auth/login/verify": [
        200,
        { access_token: "acc", refresh_token: "ref", user: userFor("inventory") },
      ],
      "GET /api/auth/me": [200, userFor("inventory")],
    });
    const user = userEvent.setup();
    renderAt("/products");

    await signInWithPassword(user);
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText("i••••••••@test.com")).toBeInTheDocument();
    expect(loadSession()).toBeNull();

    await user.type(screen.getByLabelText("Sign-in code"), "12 34 56");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Products" })).toBeInTheDocument();
    expect(loadSession().accessToken).toBe("acc");
    const verify = fetchSpy.mock.calls.find(([url]) => url.endsWith("/login/verify"));
    expect(JSON.parse(verify[1].body)).toEqual({ challenge_id: "abc123", code: "123456" });
  });

  it("shows tries left for a wrong code and stays on the code step", async () => {
    mockApi({
      "POST /api/auth/login": [200, challenge],
      "POST /api/auth/login/verify": [
        401,
        {
          error: {
            code: 401,
            message: "That code is not right. 4 tries left.",
            reason: "wrong_code",
          },
        },
      ],
    });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.type(await screen.findByLabelText("Sign-in code"), "000000");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("That code is not right. 4 tries left.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  });

  it("goes back to the password when the code has expired", async () => {
    mockApi({
      "POST /api/auth/login": [200, challenge],
      "POST /api/auth/login/verify": [
        400,
        {
          error: { code: 400, message: "This code has expired. Sign in again.", reason: "expired" },
        },
      ],
    });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.type(await screen.findByLabelText("Sign-in code"), "111111");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText("This code has expired. Sign in again.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("refuses a code that is not 6 digits without calling the server", async () => {
    const fetchSpy = mockApi({ "POST /api/auth/login": [200, challenge] });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.type(await screen.findByLabelText("Sign-in code"), "123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter the 6-digit code from the email.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => url.endsWith("/login/verify"))).toBe(false);
  });

  it("sends a new code when asked", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/login": [200, challenge],
      "POST /api/auth/login/resend": [200, { ...challenge, resend_after: 60 }],
    });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.click(await screen.findByRole("button", { name: "Send a new code" }));

    expect(await screen.findByText(/We sent a new code/)).toBeInTheDocument();
    expect(screen.getByText("Send a new code in 60s")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => url.endsWith("/login/resend"))).toBe(true);
  });

  it("lets the person start again with a different account", async () => {
    mockApi({ "POST /api/auth/login": [200, challenge] });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.click(await screen.findByRole("button", { name: "Use a different account" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});

describe("email confirmation (US-02)", () => {
  it("offers to resend the link when the email is not confirmed", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/login": [
        403,
        {
          error: {
            code: 403,
            message: "Confirm your email first.",
            reason: "email_unverified",
          },
        },
      ],
      "POST /api/auth/resend-verification": [
        200,
        { message: "If that account needs confirming, a new link is on its way." },
      ],
    });
    const user = userEvent.setup();
    renderAt("/login");

    await signInWithPassword(user);
    await user.click(await screen.findByRole("button", { name: "Send the link again" }));

    expect(await screen.findByText(/a new link is on its way/)).toBeInTheDocument();
    const call = fetchSpy.mock.calls.find(([url]) => url.endsWith("/resend-verification"));
    expect(JSON.parse(call[1].body)).toEqual({ email: "inventory@test.com" });
  });

  it("confirms the email from the link once", async () => {
    const fetchSpy = mockApi({
      "POST /api/auth/verify-email": [
        200,
        { message: "Your email is confirmed. You can sign in now." },
      ],
    });
    renderAt("/verify-email?token=tok-1");

    expect(await screen.findByRole("heading", { name: "Email confirmed" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    const calls = fetchSpy.mock.calls.filter(([url]) => url.endsWith("/verify-email"));
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0][1].body)).toEqual({ token: "tok-1" });
  });

  it("explains a bad link and sends a new one", async () => {
    mockApi({
      "POST /api/auth/verify-email": [
        400,
        {
          error: {
            code: 400,
            message: "This link is not valid or has expired.",
            reason: "link_invalid",
          },
        },
      ],
      "POST /api/auth/resend-verification": [200, { message: "A new link is on its way." }],
    });
    const user = userEvent.setup();
    renderAt("/verify-email?token=old");

    expect(
      await screen.findByRole("heading", { name: "This link did not work" }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your email"), "w@mboga.test");
    await user.click(screen.getByRole("button", { name: "Send a new link" }));
    expect(await screen.findByText("A new link is on its way.")).toBeInTheDocument();
  });

  it("sends a new business owner to sign in after the confirmation email", async () => {
    mockApi({
      "POST /api/auth/register-business": [
        201,
        {
          verification_required: true,
          message: "Mama Mboga is set up. We sent a link to w@mboga.test: open it, then sign in.",
        },
      ],
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

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText(/We sent a link to w@mboga.test/)).toBeInTheDocument();
    await waitFor(() => expect(loadSession()).toBeNull());
  });

  it("marks staff who have not confirmed their email", async () => {
    mockApi(
      {
        "GET /api/users/": [
          200,
          page([
            {
              id: 7,
              full_name: "New Hire",
              email: "new@test.com",
              role: "employee",
              is_active: true,
              email_verified: false,
            },
          ]),
        ],
      },
      "admin",
    );
    renderAt("/users", { as: "admin" });

    expect(await screen.findByText("Unconfirmed")).toBeInTheDocument();
  });
});
