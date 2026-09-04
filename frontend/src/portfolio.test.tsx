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

function savedPolicy(overrides: Record<string, unknown> = {}): Policy {
  return {
    id: "pol-1",
    user_id: "user-a",
    source_document_id: "doc-1",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    property_ids: [],
    ...extractedPolicy(),
    ...overrides,
  } as Policy;
}

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
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
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
    expect(screen.queryByLabelText(/^label$/i)).not.toBeInTheDocument();
    const addLink = screen.getByRole("link", { name: /add property/i });
    expect(addLink).toHaveAttribute("href", "/properties/new");

    await userEvent.click(addLink);
    await userEvent.type(
      await screen.findByLabelText(/^label$/i),
      "Cove Plaza",
    );
    await userEvent.type(
      screen.getByLabelText(/^address$/i),
      "100 Harbor Cove Drive",
    );
    await userEvent.type(screen.getByLabelText(/stated value/i), "25000000.00");
    await userEvent.click(
      screen.getByRole("button", { name: /add property/i }),
    );

    expect(await screen.findByText("Cove Plaza")).toBeInTheDocument();
    const list = screen.getByRole("region", { name: /properties/i });
    expect(list).toHaveTextContent("Cove Plaza");
    expect(list).toHaveTextContent("100 Harbor Cove Drive");
    expect(list).toHaveTextContent("25000000.00");
    expect(screen.queryByLabelText(/^label$/i)).not.toBeInTheDocument();
  });

  it("edits a property and returns to the list", async () => {
    let property = covePlaza();
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (
        url.endsWith("/api/v1/properties/prop-1") &&
        init?.method === "PATCH"
      ) {
        const body = JSON.parse(String(init.body)) as { label: string };
        expect(body.label).toBe("Cove Plaza North");
        property = covePlaza({ label: "Cove Plaza North" });
        return jsonResponse(200, property);
      }
      if (url.endsWith("/api/v1/properties/prop-1")) {
        return jsonResponse(200, property);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [property] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties");
    await userEvent.click(
      await screen.findByRole("link", { name: /edit cove plaza/i }),
    );
    const label = await screen.findByLabelText(/^label$/i);
    expect(label).toHaveValue("Cove Plaza");
    await userEvent.clear(label);
    await userEvent.type(label, "Cove Plaza North");
    await userEvent.click(
      screen.getByRole("button", { name: /save property/i }),
    );

    expect(await screen.findByText("Cove Plaza North")).toBeInTheDocument();
    const list = screen.getByRole("region", { name: /properties/i });
    expect(list).toHaveTextContent("Cove Plaza North");
    expect(screen.queryByLabelText(/^label$/i)).not.toBeInTheDocument();
  });

  it("does not render the property edit form until the property loads", async () => {
    let release: (value: Response) => void = () => {};
    const held = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties/prop-1")) {
        return held;
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties/prop-1/edit");
    expect(await screen.findByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^label$/i)).not.toBeInTheDocument();

    release(jsonResponse(200, covePlaza()));
    expect(await screen.findByLabelText(/^label$/i)).toHaveValue("Cove Plaza");
  });

  it("does not claim there are no properties when the list fails to load", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(500, {
          error: { code: "INTERNAL_ERROR", message: "Something went wrong." },
        });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/properties");
    expect(
      await screen.findByText("Something went wrong."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no properties yet/i)).not.toBeInTheDocument();
  });

  it("attaches a property on policy edit and shows the label on Home", async () => {
    const property = covePlaza();
    let policies: Policy[] = [savedPolicy()];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [property] });
      }
      if (url.endsWith("/api/v1/policies/pol-1") && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as {
          property_ids: string[];
        };
        expect(body.property_ids).toEqual(["prop-1"]);
        const updated = savedPolicy({ property_ids: ["prop-1"] });
        policies = [updated];
        return jsonResponse(200, updated);
      }
      if (url.endsWith("/api/v1/policies/pol-1")) {
        return jsonResponse(200, policies[0]);
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: policies });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/");
    const before = await screen.findByRole("region", {
      name: /saved policies/i,
    });
    expect(before).toHaveTextContent("Harbor Cove LLC");
    expect(before).toHaveTextContent("Building 1");
    expect(before).not.toHaveTextContent("Cove Plaza");

    await userEvent.click(
      screen.getByRole("link", { name: /edit harbor cove llc/i }),
    );
    await userEvent.click(
      await screen.findByRole("checkbox", { name: /cove plaza/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: /save policy/i }));

    const after = await screen.findByRole("region", {
      name: /saved policies/i,
    });
    expect(after).toHaveTextContent("Cove Plaza");
    expect(after).toHaveTextContent("Building 1");
  });

  it("cancels policy edit without writing", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [covePlaza()] });
      }
      if (url.endsWith("/api/v1/policies/pol-1")) {
        return jsonResponse(200, savedPolicy());
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: [savedPolicy()] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/policies/pol-1/edit");
    await userEvent.click(
      await screen.findByRole("checkbox", { name: /cove plaza/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(
      await screen.findByRole("heading", {
        name: /your insurance portfolio/i,
      }),
    ).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.some((call) => call[1]?.method === "PATCH"),
    ).toBe(false);
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
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
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

  it("deletes a policy only after the second confirm click", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    let policies: Policy[] = [savedPolicy()];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/documents")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/policies/pol-1") && init?.method === "DELETE") {
        policies = [];
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/v1/policies")) {
        return jsonResponse(200, { items: policies });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/");
    const section = await screen.findByRole("region", {
      name: /saved policies/i,
    });
    expect(section).toHaveTextContent("Harbor Cove LLC");

    await userEvent.click(
      screen.getByRole("button", { name: /delete harbor cove llc/i }),
    );
    expect(
      vi.mocked(fetch).mock.calls.some((call) => call[1]?.method === "DELETE"),
    ).toBe(false);
    expect(confirmSpy).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", {
        name: /confirm delete harbor cove llc/i,
      }),
    );
    expect(
      screen.queryByRole("region", { name: /saved policies/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Harbor Cove LLC")).not.toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          (call) =>
            String(call[0]).endsWith("/api/v1/policies/pol-1") &&
            call[1]?.method === "DELETE",
        ),
    ).toBe(true);
    confirmSpy.mockRestore();
  });

  it("still shows the policy form when properties fail to load", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/policies/pol-1")) {
        return jsonResponse(200, savedPolicy());
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(500, {
          error: { code: "INTERNAL_ERROR", message: "Something went wrong." },
        });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/policies/pol-1/edit");
    expect(
      await screen.findByRole("heading", { name: /edit policy/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/named insured/i)).toHaveValue(
      "Harbor Cove LLC",
    );
    expect(screen.getByRole("button", { name: /save policy/i })).toBeEnabled();
    expect(
      await screen.findByText("Unable to load properties."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no properties yet/i)).not.toBeInTheDocument();
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
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
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
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/properties");
    await userEvent.click(
      await screen.findByRole("link", { name: /add property/i }),
    );
    await userEvent.type(await screen.findByLabelText(/^label$/i), "   ");
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
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/properties");
    expect(await screen.findByText("Mine Plaza")).toBeInTheDocument();
    expect(screen.queryByText("Theirs Plaza")).not.toBeInTheDocument();
    expect(screen.queryByText("user-b")).not.toBeInTheDocument();
  });
});
