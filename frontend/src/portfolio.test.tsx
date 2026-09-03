import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth";
import { AppRoutes } from "./App";

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

function covePlaza(overrides: Record<string, unknown> = {}) {
  return {
    id: "prop-1",
    user_id: "user-a",
    label: "Cove Plaza",
    address: "100 Harbor Cove Drive",
    stated_value: "25000000.00",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    policy_ids: [],
    ...overrides,
  };
}

describe("portfolio management", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a property and shows it on /properties", async () => {
    const created = covePlaza();
    let properties: ReturnType<typeof covePlaza>[] = [];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          label: string;
          address?: string | null;
          stated_value?: string | null;
        };
        expect(body.label).toBe("Cove Plaza");
        expect(body.address).toBe("100 Harbor Cove Drive");
        expect(body.stated_value).toBe("25000000.00");
        properties = [created];
        return jsonResponse(201, created);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: properties });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties");
    expect(
      await screen.findByRole("heading", { name: /^properties$/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^properties$/i })).toHaveAttribute(
      "href",
      "/properties",
    );
    expect(screen.queryByText("Cove Plaza")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/^label$/i), "Cove Plaza");
    await userEvent.type(
      screen.getByLabelText(/^address$/i),
      "100 Harbor Cove Drive",
    );
    await userEvent.type(screen.getByLabelText(/stated value/i), "25000000.00");
    await userEvent.click(
      screen.getByRole("button", { name: /add property/i }),
    );

    const list = await screen.findByRole("region", { name: /properties/i });
    expect(list).toHaveTextContent("Cove Plaza");
    expect(list).toHaveTextContent("100 Harbor Cove Drive");
    expect(list).toHaveTextContent("25000000.00");
  });

  it("deletes a property only after the second confirm click", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    let properties = [covePlaza({ policy_ids: ["pol-1", "pol-2"] })];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/properties/prop-1") &&
        init?.method === "DELETE"
      ) {
        properties = [];
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: properties });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties");
    expect(await screen.findByText("Cove Plaza")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /delete cove plaza/i }),
    );
    expect(
      vi.mocked(fetch).mock.calls.some((call) => call[1]?.method === "DELETE"),
    ).toBe(false);
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(screen.getByText(/unlink it from 2 policies/i)).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /confirm delete cove plaza/i }),
    );
    expect(screen.queryByText("Cove Plaza")).not.toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          (call) =>
            String(call[0]).endsWith("/api/v1/properties/prop-1") &&
            call[1]?.method === "DELETE",
        ),
    ).toBe(true);
    confirmSpy.mockRestore();
  });

  it("does not claim an unattached property is linked to 0 policies", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [covePlaza()] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/properties");
    await userEvent.click(
      await screen.findByRole("button", { name: /delete cove plaza/i }),
    );
    expect(screen.getByText(/delete cove plaza\?/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/unlink it from 0 policies/i),
    ).not.toBeInTheDocument();
  });

  it("requires a non-empty label and surfaces invalid stated value", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          stated_value?: string | null;
        };
        if (body.stated_value === "approx 25M") {
          return jsonResponse(422, {
            error: {
              code: "VALIDATION_ERROR",
              message: "stated_value: Value error, must be a money amount",
            },
          });
        }
        throw new Error(`unexpected create ${JSON.stringify(body)}`);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties");
    await screen.findByRole("heading", { name: /^properties$/i });
    await userEvent.type(screen.getByLabelText(/^label$/i), "   ");
    await userEvent.click(
      screen.getByRole("button", { name: /add property/i }),
    );
    expect(await screen.findByText("Label is required.")).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.some((call) => call[1]?.method === "POST"),
    ).toBe(false);

    await userEvent.clear(screen.getByLabelText(/^label$/i));
    await userEvent.type(screen.getByLabelText(/^label$/i), "Cove Plaza");
    await userEvent.type(screen.getByLabelText(/stated value/i), "approx 25M");
    await userEvent.click(
      screen.getByRole("button", { name: /add property/i }),
    );
    expect(
      await screen.findByText(/must be a money amount/i),
    ).toBeInTheDocument();
  });

  it("never shows another user's properties in the list mock", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, {
          items: [covePlaza({ label: "Mine Plaza" })],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/properties");
    expect(await screen.findByText("Mine Plaza")).toBeInTheDocument();
    expect(screen.queryByText("Theirs Plaza")).not.toBeInTheDocument();
    expect(screen.queryByText("user-b")).not.toBeInTheDocument();
  });
});
