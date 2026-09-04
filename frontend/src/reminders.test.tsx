import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders, AppRoutes } from "./App";
import type { ExtractedPolicy, Policy, Reminder } from "./api";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </MemoryRouter>,
  );
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const owner = {
  id: "user-a",
  email: "owner@example.com",
  created_at: "2026-01-01T00:00:00Z",
};

function extractedPolicy(
  overrides: Partial<ExtractedPolicy> = {},
): ExtractedPolicy {
  return {
    policy_number: "HCL-2024-4412",
    named_insured: "Harbor Cove LLC",
    broker: "Northshore Risk Partners",
    effective_date: "2024-01-01",
    renewal_date: "2026-10-03",
    term_premium: "185000.00",
    policy_fee: "1500.00",
    total_premium: "186500.00",
    limit_of_insurance: "25000000.00",
    coverage_type: "Property",
    carriers: ["Acme Insurance Company"],
    deductibles: [{ peril: "Wind/Hail", amount: "50000.00" }],
    locations: [{ label: "Building 1", address: "100 Harbor Cove Drive" }],
    confidence: {
      policy_number: 0.92,
      named_insured: 0.95,
      broker: 0.4,
      effective_date: 0.9,
      renewal_date: 0.9,
      term_premium: 0.88,
      policy_fee: 0.7,
      total_premium: 0.88,
      limit_of_insurance: 0.91,
      coverage_type: 0.85,
      carriers: 0.9,
      deductibles: 0.93,
      locations: 0.87,
    },
    ...overrides,
  };
}

function savedPolicy(overrides: Partial<Policy> = {}): Policy {
  return {
    id: "pol-1",
    user_id: "user-a",
    source_document_id: "doc-1",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    property_ids: [],
    ...extractedPolicy(),
    ...overrides,
  };
}

function reminder(overrides: Partial<Reminder> = {}): Reminder {
  return {
    id: "rem-30",
    policy_id: "pol-1",
    threshold_days: 30,
    renewal_date: "2026-10-03",
    read_at: null,
    named_insured: "Harbor Cove LLC",
    coverage_type: "Property",
    ...overrides,
  };
}

describe("renewal reminders", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an unread count on the Shell Reminders link", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, {
          items: [reminder(), reminder({ id: "rem-60", threshold_days: 60 })],
          unread_count: 2,
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(
      await screen.findByRole("link", { name: /reminders, 2 unread/i }),
    ).toBeInTheDocument();
  });

  it("lists reminder copy and a view link to policy detail", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, {
          items: [reminder()],
          unread_count: 1,
        });
      }
      if (url.endsWith("/api/v1/policies/pol-1/history")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies/pol-1")) {
        return jsonResponse(200, savedPolicy());
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/reminders");
    expect(
      await screen.findByText(
        /Harbor Cove LLC · Property · 30-day reminder · renews 2026-10-03/,
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("link", { name: /view harbor cove llc/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /harbor cove llc/i }),
    ).toBeInTheDocument();
  });

  it("mark as read drops the unread count", async () => {
    let unread = 1;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/reminders/rem-30/read") &&
        init?.method === "POST"
      ) {
        unread = 0;
        return jsonResponse(200, reminder({ read_at: "2026-09-03T12:00:00Z" }));
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, {
          items: [
            reminder({ read_at: unread === 0 ? "2026-09-03T12:00:00Z" : null }),
          ],
          unread_count: unread,
        });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/reminders");
    expect(
      await screen.findByRole("link", { name: /reminders, 1 unread/i }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /mark harbor cove llc as read/i }),
    );
    expect(
      await screen.findByRole("link", { name: /^reminders$/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /reminders, 1 unread/i }),
    ).not.toBeInTheDocument();
  });

  it("mark as unread restores the unread count", async () => {
    let unread = 0;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/reminders/rem-30/unread") &&
        init?.method === "POST"
      ) {
        unread = 1;
        return jsonResponse(200, reminder({ read_at: null }));
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, {
          items: [
            reminder({ read_at: unread === 0 ? "2026-09-03T12:00:00Z" : null }),
          ],
          unread_count: unread,
        });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/reminders");
    expect(
      await screen.findByRole("heading", { name: /^read$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /^reminders$/i }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /mark harbor cove llc as unread/i }),
    );
    expect(
      await screen.findByRole("link", { name: /reminders, 1 unread/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /^unread$/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /^read$/i }),
    ).not.toBeInTheDocument();
  });

  it("does not flash an empty list before reminders load", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/reminders")) {
        await gate;
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/reminders");
    expect(await screen.findByText(/loading/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/no renewal reminders right now/i),
    ).not.toBeInTheDocument();
    release();
    expect(
      await screen.findByText(/no renewal reminders right now/i),
    ).toBeInTheDocument();
  });

  it("keeps the unread count when navigating between pages", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, {
          items: [reminder(), reminder({ id: "rem-60", threshold_days: 60 })],
          unread_count: 2,
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(
      await screen.findByRole("link", { name: /reminders, 2 unread/i }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("link", { name: /reminders, 2 unread/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /^reminders$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /reminders, 2 unread/i }),
    ).toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/reminders");
    expect(
      await screen.findByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });
});
