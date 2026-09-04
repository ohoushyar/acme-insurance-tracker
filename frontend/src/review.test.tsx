import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders, AppRoutes } from "./App";
import type { DocumentJob, ExtractedPolicy } from "./api";

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
    deductibles: [
      { peril: "Wind/Hail", amount: "50000.00" },
      { peril: "All Other Perils", amount: "25000.00" },
    ],
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

describe("review confirm screen", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows extracted fields with confidence and flags low-confidence values", async () => {
    const job = completedJob({
      extracted: extractedPolicy({
        named_insured: null,
        confidence: {
          ...extractedPolicy().confidence,
          named_insured: 0,
        },
      }),
    });
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, job);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/documents/doc-1/review");
    expect(
      await screen.findByRole("heading", { name: /review extracted fields/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/policy number/i)).toHaveValue(
      "HCL-2024-4412",
    );
    expect(screen.getByLabelText(/named insured/i)).toHaveValue("");
    expect(screen.getByLabelText(/limit of insurance/i)).toHaveValue(
      "$25,000,000",
    );
    expect(screen.getByText("92%")).not.toHaveClass("confidence-low");
    expect(screen.getByText("40%")).toHaveClass("confidence-low");
    expect(screen.getByText(/missing or low confidence/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /view original pdf/i }),
    ).toHaveAttribute("href", "/api/v1/documents/doc-1/file");
  });

  it("lets the user edit fields and confirm, then returns home as reviewed", async () => {
    const completed = completedJob();
    let stored: DocumentJob = completed;
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
        expect(body.named_insured).toBe("Harbor Cove HOA");
        expect(body.confidence.named_insured).toBe(1);
        expect(
          body.deductibles.some((item) => item.peril === "Wind/Hail"),
        ).toBe(false);
        expect(
          body.deductibles.some(
            (item) =>
              item.peril === "Named Hurricane" &&
              item.amount === "3% (min $50,000)",
          ),
        ).toBe(true);
        stored = {
          ...completed,
          status: "reviewed",
          extracted: body,
        };
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
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/documents/doc-1/review");
    const namedInsured = await screen.findByLabelText(/named insured/i);
    await userEvent.clear(namedInsured);
    await userEvent.type(namedInsured, "Harbor Cove HOA");

    await userEvent.click(
      screen.getByRole("button", { name: /remove deductible wind\/hail/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add deductible/i }),
    );
    const perilInputs = screen.getAllByLabelText(/^peril$/i);
    const amountInputs = screen.getAllByLabelText(/^amount$/i);
    await userEvent.type(
      perilInputs[perilInputs.length - 1],
      "Named Hurricane",
    );
    await userEvent.type(
      amountInputs[amountInputs.length - 1],
      "3% (min $50,000)",
    );

    await userEvent.click(
      screen.getByRole("button", { name: /looks right — confirm/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            (call) =>
              String(call[0]).endsWith("/api/v1/documents/doc-1/confirm") &&
              call[1]?.method === "POST",
          ),
      ).toBe(true);
    });
  });

  it("does not confirm when the user cancels", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, completedJob());
      }
      if (
        url.endsWith("/api/v1/documents") &&
        (!init || init.method === undefined || init.method === "GET")
      ) {
        return jsonResponse(200, { items: [completedJob()] });
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/documents/doc-1/review");
    await screen.findByRole("heading", { name: /review extracted fields/i });
    await userEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(
      await screen.findByRole("heading", { name: /^uploads$/i }),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some((call) => String(call[0]).includes("/confirm")),
    ).toBe(false);
  });

  it("redirects unauthenticated visitors from the review screen to login", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(401, {
        error: { code: "UNAUTHENTICATED", message: "Please sign in." },
      }),
    );
    renderAt("/documents/doc-1/review");
    expect(
      await screen.findByRole("heading", { name: /insurance tracker/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it("offers a review link on Uploads for completed jobs instead of the full field grid", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [completedJob()] });
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

    renderAt("/uploads");
    expect(
      await screen.findByRole("link", { name: /review extracted fields/i }),
    ).toHaveAttribute("href", "/documents/doc-1/review");
    expect(screen.getByText("Harbor Cove LLC")).toBeInTheDocument();
    expect(screen.queryByText(/Wind\/Hail/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Building 1/)).not.toBeInTheDocument();
  });

  it("renders a sparse extraction payload without crashing", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, {
          ...completedJob(),
          extracted: { named_insured: "Harbor Cove LLC" },
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

    renderAt("/documents/doc-1/review");
    expect(
      await screen.findByRole("heading", { name: /review extracted fields/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/named insured/i)).toHaveValue(
      "Harbor Cove LLC",
    );
    expect(screen.getByLabelText(/policy number/i)).toHaveValue("");
    expect(
      screen.getByRole("button", { name: /add deductible/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/missing or low confidence/i)).toBeInTheDocument();
  });
});
