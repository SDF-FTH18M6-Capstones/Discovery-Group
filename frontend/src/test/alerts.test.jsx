import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "./helpers";

describe("phone link", () => {
  it("makes a private link once, with setup steps, and can unlink", async () => {
    let removed = false;
    mockApi(
      {
        "GET /api/phone/link": [200, { active: false, url: null, messages: 0 }],
        "POST /api/phone/link": [
          201,
          {
            active: true,
            url: "https://api.example.com/api/phone/inbox/secret-token",
            created_at: "2026-11-28T08:00:00Z",
            last_message_at: null,
            messages: 0,
          },
        ],
        "DELETE /api/phone/link": () => {
          removed = true;
          return [204, null];
        },
      },
      "admin",
    );
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderAt("/money", { as: "admin" });

    await user.click(await screen.findByRole("button", { name: "Link a phone" }));

    expect(screen.getByText("https://api.example.com/api/phone/inbox/secret-token")).toBeVisible();
    expect(screen.getByRole("link", { name: "SMS to URL Forwarder" })).toHaveAttribute(
      "href",
      "https://f-droid.org/packages/tech.bogomolov.incomingsmsgateway/",
    );
    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith("https://api.example.com/api/phone/inbox/secret-token");
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Unlink" }));
    expect(removed).toBe(true);
    expect(await screen.findByRole("button", { name: "Link a phone" })).toBeInTheDocument();
  });

  it("shows how a linked phone is doing", async () => {
    mockApi(
      {
        "GET /api/phone/link": [
          200,
          {
            active: true,
            url: null,
            created_at: "2026-11-20T08:00:00Z",
            last_message_at: "2026-11-27T15:40:00Z",
            messages: 42,
          },
        ],
      },
      "admin",
    );
    renderAt("/money", { as: "admin" });

    expect(await screen.findByText(/42 messages so far/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Make a new link" })).toBeInTheDocument();
  });
});

describe("WhatsApp alerts", () => {
  it("saves the number, explains when sending isn't set up, and sends a test", async () => {
    let saved = null;
    mockApi(
      {
        "GET /api/business/whatsapp": [
          200,
          { whatsapp_number: null, whatsapp_alerts: false, connected: false },
        ],
        "PUT /api/business/whatsapp": (options) => {
          saved = JSON.parse(options.body);
          return [
            200,
            { whatsapp_number: "254712345678", whatsapp_alerts: true, connected: false },
          ];
        },
        "POST /api/business/whatsapp/test": [200, { sent: true }],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "admin" });

    expect(await screen.findByText(/isn't set up on the server yet/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("WhatsApp number"), "0712 345 678");
    await user.click(screen.getByLabelText("Send alerts to this number"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(saved).toEqual({ whatsapp_number: "0712 345 678", whatsapp_alerts: true });
    await user.click(await screen.findByRole("button", { name: "Send a test message" }));
    expect(await screen.findByText(/the test was only recorded/)).toBeInTheDocument();
  });

  it("shows the server's reason when saving fails", async () => {
    mockApi(
      {
        "GET /api/business/whatsapp": [
          200,
          { whatsapp_number: null, whatsapp_alerts: false, connected: true },
        ],
        "PUT /api/business/whatsapp": [
          422,
          { error: { message: "Add the WhatsApp number that should get the alerts." } },
        ],
      },
      "admin",
    );
    const user = userEvent.setup();
    renderAt("/settings", { as: "admin" });

    await user.click(await screen.findByLabelText("Send alerts to this number"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/Add the WhatsApp number/)).toBeInTheDocument();
    expect(screen.queryByText(/isn't set up on the server yet/)).not.toBeInTheDocument();
  });
});

describe("loan-readiness report", () => {
  it("downloads the PDF for the chosen months", async () => {
    const spy = mockApi(
      { "GET /api/reports/summary": [500, { error: { message: "Not needed here" } }] },
      "admin",
    );
    const answer = spy.getMockImplementation();
    const asked = [];
    spy.mockImplementation(async (url, options) => {
      if (String(url).includes("performance.pdf")) {
        asked.push(new URL(url).search);
        return { ok: true, status: 200, blob: async () => new Blob(["%PDF-1.4"]) };
      }
      return answer(url, options);
    });
    URL.createObjectURL = vi.fn(() => "blob:report");
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const user = userEvent.setup();
    renderAt("/reports", { as: "admin" });

    await user.selectOptions(await screen.findByLabelText("Covering"), "12");
    await user.click(screen.getByRole("button", { name: /Download PDF/ }));

    expect(asked).toEqual(["?months=12"]);
    expect(click).toHaveBeenCalled();
  });
});
