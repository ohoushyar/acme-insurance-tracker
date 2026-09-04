import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders, AppRoutes } from "./App";
import type { ExtractedPolicy, Policy } from "./api";

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
    renewal_date: "2025-01-01",
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

describe("dashboard urgency groups", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-01T12:00:00Z"));
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows summary stats and urgency group headings", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, {
          items: [
            savedPolicy({
              id: "urgent",
              named_insured: "Urgent LLC",
              renewal_date: "2026-09-14",
              total_premium: "10000",
            }),
            savedPolicy({
              id: "soon",
              named_insured: "Soon LLC",
              renewal_date: "2026-10-20",
              total_premium: "20000",
            }),
            savedPolicy({
              id: "track",
              named_insured: "Track LLC",
              renewal_date: "2027-01-18",
              total_premium: "30000",
            }),
          ],
        });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    const summary = await screen.findByRole("region", {
      name: /portfolio summary/i,
    });
    expect(summary).toHaveTextContent("Total annual premium");
    expect(summary).toHaveTextContent("$60,000");
    expect(summary).toHaveTextContent("Renewing within 30 days");
    expect(summary).toHaveTextContent("Renewing within 90 days");
    expect(summary).toHaveTextContent("Premium up 10%+");
    expect(
      screen.getByRole("heading", { name: /renews within 30 days/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /renews within 90 days/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /on track/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/drop pdfs here or choose files/i),
    ).toBeInTheDocument();
  });

  it("hides the stat strip when there are no policies", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(
      await screen.findByLabelText(/drop pdfs here or choose files/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: /portfolio summary/i }),
    ).not.toBeInTheDocument();
  });
});
