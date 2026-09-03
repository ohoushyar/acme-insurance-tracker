import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth";
import { AppRoutes } from "./App";
import type { DocumentJob, ExtractedPolicy, Policy } from "./api";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
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
    deductibles: [
      { peril: "Wind/Hail", amount: "50000.00" },
      { peril: "All Other Perils", amount: "25000.00" },
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
    property_ids: [],
    ...extractedPolicy(),
    ...overrides,
  };
}

function completedJob(overrides: Partial<DocumentJob> = {}): DocumentJob {
  return {
    id: "doc-1",
    user_id: "user-a",
    original_filename: "harbor.pdf",
    content_type: "application/pdf",
    byte_size: 128,
    status: "completed",
    extracted: extractedPolicy(),
    error_code: null,
    error_message: null,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    policy_id: null,
    ...overrides,
  };
}

describe("saved policies", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists confirmed policies on Home with locations", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, {
          items: [completedJob({ status: "reviewed", policy_id: "pol-1" })],
        });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(
      await screen.findByRole("heading", { name: /saved policies/i }),
    ).toBeInTheDocument();
    const section = screen.getByRole("region", { name: /saved policies/i });
    expect(section).toHaveTextContent("Harbor Cove LLC");
    expect(section).toHaveTextContent("HCL-2024-4412");
    expect(section).toHaveTextContent("Property");
    expect(section).toHaveTextContent("2025-01-01");
    expect(section).toHaveTextContent("186500.00");
    expect(section).toHaveTextContent("Building 1");
    expect(section).toHaveTextContent("Building 3");
  });

  it("does not render another user's policies from the list payload", async () => {
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
          items: [savedPolicy({ named_insured: "Mine LLC" })],
        });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(await screen.findByText("Mine LLC")).toBeInTheDocument();
    expect(screen.queryByText("Theirs LLC")).not.toBeInTheDocument();
    expect(screen.queryByText("user-b")).not.toBeInTheDocument();
  });

  it("shows the confirmed policy on Home after review confirm", async () => {
    const completed = completedJob();
    let stored: DocumentJob = completed;
    let policies: Policy[] = [];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/documents/doc-1/confirm") &&
        init?.method === "POST"
      ) {
        const body = JSON.parse(String(init.body)) as ExtractedPolicy;
        stored = {
          ...completed,
          status: "reviewed",
          extracted: body,
          policy_id: "pol-1",
        };
        policies = [
          savedPolicy({
            named_insured: body.named_insured,
            locations: body.locations,
          }),
        ];
        return jsonResponse(200, stored);
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, stored);
      }
      if (
        url.endsWith("/api/v1/documents") &&
        (!init || init.method === undefined || init.method === "GET")
      ) {
        return jsonResponse(200, { items: [stored] });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: policies });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/documents/doc-1/review");
    const namedInsured = await screen.findByLabelText(/named insured/i);
    await userEvent.clear(namedInsured);
    await userEvent.type(namedInsured, "Harbor Cove HOA");
    await userEvent.click(
      screen.getByRole("button", { name: /looks right — confirm/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /saved policies/i }),
    ).toBeInTheDocument();
    const section = screen.getByRole("region", { name: /saved policies/i });
    expect(section).toHaveTextContent("Harbor Cove HOA");
    expect(section).toHaveTextContent("Building 1");
  });

  it("still lists documents when saved policies fail to load", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, {
          items: [
            completedJob({
              original_filename: "mine.pdf",
              status: "completed",
            }),
          ],
        });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(500, {
          error: { code: "INTERNAL_ERROR", message: "Something went wrong." },
        });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    expect(await screen.findByText("mine.pdf")).toBeInTheDocument();
    expect(
      await screen.findByText("Unable to load saved policies."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /saved policies/i }),
    ).not.toBeInTheDocument();
  });

  it("still lists saved policies when properties fail to load", async () => {
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
        return jsonResponse(500, {
          error: { code: "INTERNAL_ERROR", message: "Something went wrong." },
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/");
    const section = await screen.findByRole("region", {
      name: /saved policies/i,
    });
    expect(section).toHaveTextContent("Harbor Cove LLC");
    expect(section).toHaveTextContent("Building 1");
    expect(
      await screen.findByText("Unable to load properties."),
    ).toBeInTheDocument();
  });
});
