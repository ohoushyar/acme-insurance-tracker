import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders, AppRoutes } from "./App";

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

describe("auth screens", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("redirects unauthenticated visitors from / to /login", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(401, {
        error: { code: "UNAUTHENTICATED", message: "Please sign in." },
      }),
    );
    renderAt("/");
    expect(
      await screen.findByRole("heading", { name: /insurance tracker/i }),
    ).toBeInTheDocument();
  });

  it("submits login credentials and redirects home on success", async () => {
    const user = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (
        url.endsWith("/api/v1/auth/me") &&
        (!init || init.method === undefined || init.method === "GET")
      ) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (url.endsWith("/api/v1/auth/login") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          email: "owner@example.com",
          password: "correct-horse",
        });
        return jsonResponse(200, user);
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/login");
    await userEvent.type(
      await screen.findByLabelText(/email/i),
      "owner@example.com",
    );
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();
  });

  it("shows the API error message when login fails", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (url.endsWith("/api/v1/auth/login")) {
        return jsonResponse(401, {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Email or password is incorrect.",
          },
        });
      }
      if (url.endsWith("/api/v1/properties")) {
        return jsonResponse(200, { items: [] });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/login");
    await userEvent.type(
      await screen.findByLabelText(/email/i),
      "owner@example.com",
    );
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(
      await screen.findByText("Email or password is incorrect."),
    ).toBeInTheDocument();
  });

  it("submits register payload and lands on the portfolio shell", async () => {
    const user = {
      id: "u1",
      email: "new@example.com",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (url.endsWith("/api/v1/auth/register") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          email: "new@example.com",
          password: "correct-horse",
        });
        return jsonResponse(201, user);
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/register");
    await userEvent.type(
      await screen.findByLabelText(/email/i),
      "new@example.com",
    );
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse");
    await userEvent.click(
      screen.getByRole("button", { name: /create account/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    const user = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
    };
    let signedIn = true;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return signedIn
          ? jsonResponse(200, user)
          : jsonResponse(401, {
              error: { code: "UNAUTHENTICATED", message: "Please sign in." },
            });
      }
      if (url.endsWith("/api/v1/auth/logout") && init?.method === "POST") {
        signedIn = false;
        return new Response(null, { status: 204 });
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/");
    expect(
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(
      await screen.findByRole("heading", { name: /insurance tracker/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([url, init]) =>
              String(url).endsWith("/api/v1/auth/logout") &&
              init?.method === "POST",
          ),
      ).toBe(true);
    });
  });

  it("sends a forgot-password request and shows confirmation", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (
        url.endsWith("/api/v1/auth/forgot-password") &&
        init?.method === "POST"
      ) {
        expect(JSON.parse(String(init.body))).toEqual({
          email: "owner@example.com",
        });
        return new Response(null, { status: 204 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });
    renderAt("/forgot-password");
    await userEvent.type(
      await screen.findByLabelText(/email/i),
      "owner@example.com",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /send reset link/i }),
    );
    expect(
      await screen.findByText(/if an account exists for that address/i),
    ).toBeInTheDocument();
  });

  it("submits a new password from the reset screen", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (
        url.endsWith("/api/v1/auth/reset-password") &&
        init?.method === "POST"
      ) {
        expect(JSON.parse(String(init.body))).toEqual({
          token: "reset-token",
          password: "new-horse-1",
        });
        return new Response(null, { status: 204 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });
    renderAt("/reset-password?token=reset-token");
    await userEvent.type(
      await screen.findByLabelText(/^new password$/i),
      "new-horse-1",
    );
    await userEvent.type(
      screen.getByLabelText(/confirm password/i),
      "new-horse-1",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /update password/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /insurance tracker/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it("shows a verification banner when email_verified_at is null", async () => {
    const user = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
      email_verified_at: null,
    };
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, user);
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
      await screen.findByText(
        /verify your email to receive renewal reminders/i,
      ),
    ).toBeInTheDocument();
  });

  it("does not show a verification banner when the address is verified", async () => {
    const user = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
      email_verified_at: "2026-01-02T00:00:00Z",
    };
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, user);
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
      await screen.findByRole("heading", { name: /your insurance portfolio/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/verify your email to receive renewal reminders/i),
    ).not.toBeInTheDocument();
  });

  it("verifies email from the token query string when signed in", async () => {
    const unverified = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
      email_verified_at: null,
    };
    const verified = {
      ...unverified,
      email_verified_at: "2026-01-02T00:00:00Z",
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, unverified);
      }
      if (
        url.endsWith("/api/v1/auth/verify-email") &&
        init?.method === "POST"
      ) {
        expect(JSON.parse(String(init.body))).toEqual({
          token: "verify-token",
        });
        return jsonResponse(200, verified);
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });
    renderAt("/verify-email?token=verify-token");
    expect(
      await screen.findByRole("heading", {
        name: /your insurance portfolio/i,
      }),
    ).toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in after verifying", async () => {
    const verified = {
      id: "u1",
      email: "owner@example.com",
      created_at: "2026-01-01T00:00:00Z",
      email_verified_at: "2026-01-02T00:00:00Z",
    };
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(401, {
          error: { code: "UNAUTHENTICATED", message: "Please sign in." },
        });
      }
      if (
        url.endsWith("/api/v1/auth/verify-email") &&
        init?.method === "POST"
      ) {
        expect(JSON.parse(String(init.body))).toEqual({
          token: "verify-token",
        });
        return jsonResponse(200, verified);
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });
    renderAt("/verify-email?token=verify-token");
    expect(
      await screen.findByText(/your email is verified/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(
      screen.queryByRole("heading", { name: /your insurance portfolio/i }),
    ).not.toBeInTheDocument();
  });
});
