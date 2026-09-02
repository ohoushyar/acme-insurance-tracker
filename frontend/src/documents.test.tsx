import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth";
import { AppRoutes } from "./App";
import type { DocumentJob } from "./api";

function renderHome() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
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

function pendingJob(): DocumentJob {
  return {
    id: "doc-1",
    user_id: "user-a",
    original_filename: "harbor.pdf",
    content_type: "application/pdf",
    byte_size: 128,
    status: "pending",
    extracted: null,
    error_code: null,
    error_message: null,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  };
}

describe("document upload", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts polling after a successful upload and shows extracted fields", async () => {
    const completed: DocumentJob = {
      ...pendingJob(),
      status: "completed",
      extracted: {
        policy_number: "HCL-2024-4412",
        named_insured: "Harbor Cove LLC",
        broker: null,
        effective_date: "2024-01-01",
        renewal_date: "2025-01-01",
        term_premium: "185000.00",
        policy_fee: null,
        total_premium: "186500.00",
        limit_of_insurance: null,
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
          broker: 0,
          effective_date: 0.9,
          renewal_date: 0.9,
          term_premium: 0.88,
          policy_fee: 0,
          total_premium: 0.88,
          limit_of_insurance: 0,
          coverage_type: 0.85,
          carriers: 0.9,
          deductibles: 0.93,
          locations: 0.87,
        },
      },
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/documents") &&
        (!init || init.method === undefined || init.method === "GET")
      ) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/documents") && init?.method === "POST") {
        expect(init.body).toBeInstanceOf(FormData);
        return jsonResponse(202, { items: [pendingJob()] });
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, completed);
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderHome();
    expect(
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();

    const file = new File(["%PDF-1.4"], "harbor.pdf", {
      type: "application/pdf",
    });
    await userEvent.upload(
      screen.getByLabelText(/drop pdfs here or choose files/i),
      file,
    );

    expect(await screen.findByText("Harbor Cove LLC")).toBeInTheDocument();
    expect(screen.getByText(/Wind\/Hail/)).toBeInTheDocument();
    expect(screen.getByText(/Building 1/)).toBeInTheDocument();
    await waitFor(() => {
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some((call) =>
            String(call[0]).endsWith("/api/v1/documents/doc-1"),
          ),
      ).toBe(true);
    });
  });

  it("shows the API error message when extraction fails", async () => {
    const failed: DocumentJob = {
      ...pendingJob(),
      status: "failed",
      error_code: "EXTRACTION_FAILED",
      error_message: "This document looks scanned or has no extractable text.",
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/documents") &&
        (!init || init.method === undefined || init.method === "GET")
      ) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/documents") && init?.method === "POST") {
        return jsonResponse(202, { items: [pendingJob()] });
      }
      if (url.endsWith("/api/v1/documents/doc-1")) {
        return jsonResponse(200, failed);
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderHome();
    await screen.findByRole("heading", { name: /your insurance portfolio/i });
    const file = new File(["%PDF-1.4"], "harbor.pdf", {
      type: "application/pdf",
    });
    await userEvent.upload(
      screen.getByLabelText(/drop pdfs here or choose files/i),
      file,
    );
    expect(
      await screen.findByText(
        "This document looks scanned or has no extractable text.",
      ),
    ).toBeInTheDocument();
  });

  it("does not render another user's documents from the list payload", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, {
          items: [
            {
              ...pendingJob(),
              status: "completed",
              original_filename: "mine.pdf",
            },
          ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderHome();
    expect(await screen.findByText("mine.pdf")).toBeInTheDocument();
    expect(screen.queryByText("theirs.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("user-b")).not.toBeInTheDocument();
  });
});
