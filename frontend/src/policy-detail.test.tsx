import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    carriers: ["Acme Insurance Company", "Indian Harbor"],
    deductibles: [
      { peril: "Named Hurricane", amount: "3% (min $50,000)" },
      { peril: "All Other Perils", amount: "$5,000 per occurrence" },
    ],
    locations: [
      { label: "Building 1", address: "100 Harbor Cove Drive" },
      { label: "Building 3", address: "120 Harbor Cove Drive" },
    ],
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
    property_ids: ["prop-1"],
    ...extractedPolicy(),
    ...overrides,
  };
}

function covePlaza() {
  return {
    id: "prop-1",
    user_id: "user-a",
    label: "Cove Plaza",
    address: "100 Harbor Cove Drive",
    stated_value: "25000000.00",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    policy_ids: ["pol-1"],
  };
}

describe("policy detail", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders all Harbor Cove–shaped fields read-only", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
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
        return jsonResponse(200, { items: [covePlaza()] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/policies/pol-1");

    expect(
      await screen.findByRole("heading", { name: /harbor cove llc/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("HCL-2024-4412")).toBeInTheDocument();
    expect(screen.getByText("Acme Insurance Company")).toBeInTheDocument();
    expect(screen.getByText("Indian Harbor")).toBeInTheDocument();
    expect(screen.getByText("Named Hurricane")).toBeInTheDocument();
    expect(screen.getByText("3% (min $50,000)")).toBeInTheDocument();
    expect(screen.getByText("All Other Perils")).toBeInTheDocument();
    expect(screen.getByText("Building 1")).toBeInTheDocument();
    expect(screen.getByText("100 Harbor Cove Drive")).toBeInTheDocument();
    expect(screen.getByText("Cove Plaza")).toBeInTheDocument();
    expect(
      screen.getByText(/named insured/i).closest(".detail-line"),
    ).toHaveTextContent("95%");
    expect(
      screen.getByRole("link", { name: /edit harbor cove llc/i }),
    ).toHaveAttribute("href", "/policies/pol-1/edit");
    expect(
      screen.getByRole("link", { name: /source document/i }),
    ).toHaveAttribute("href", "/documents/doc-1/review");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows a plain-language error when the policy is missing", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/policies/missing")) {
        return jsonResponse(404, {
          error: { code: "NOT_FOUND", message: "Policy not found." },
        });
      }
      if (url.endsWith("/api/v1/policies/missing/history")) {
        return jsonResponse(404, {
          error: { code: "NOT_FOUND", message: "Policy not found." },
        });
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

    renderAt("/policies/missing");
    expect(await screen.findByText("Policy not found.")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHORIZED", message: "Not authenticated." },
        });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/policies/pol-1");
    expect(
      await screen.findByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it("opens detail from the Home View link", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies/pol-1/history")) {
        return jsonResponse(200, {
          items: [
            { year: 2023, premium: "100000", policy_id: "pol-0" },
            { year: 2024, premium: "186500.00", policy_id: "pol-1" },
          ],
        });
      }
      if (url.endsWith("/api/v1/policies/pol-1")) {
        return jsonResponse(
          200,
          savedPolicy({ yoy_change_pct: 20, yoy_flagged: true }),
        );
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [covePlaza()] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    await userEvent.click(
      await screen.findByRole("link", { name: /view harbor cove llc/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /harbor cove llc/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Named Hurricane")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /premium history/i }),
    ).toBeInTheDocument();
  });
});
