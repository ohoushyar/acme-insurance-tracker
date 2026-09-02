import { render, screen, waitFor } from "@testing-library/react";
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/login");
    await userEvent.type(
      await screen.findByLabelText(/email/i),
      "owner@example.com",
    );
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/portfolio insurance/i)).toBeInTheDocument();
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
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
    expect(await screen.findByText(/portfolio insurance/i)).toBeInTheDocument();
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
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/");
    expect(await screen.findByText(/portfolio insurance/i)).toBeInTheDocument();
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
});
