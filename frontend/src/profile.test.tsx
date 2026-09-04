import { render, screen } from "@testing-library/react";
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

const owner = {
  id: "user-a",
  email: "owner@example.com",
  created_at: "2026-01-01T00:00:00Z",
};

describe("profile password", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("redirects unauthenticated visitors from /profile to /login", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(401, {
        error: { code: "UNAUTHENTICATED", message: "Please sign in." },
      }),
    );
    renderAt("/profile");
    expect(
      await screen.findByRole("heading", { name: /insurance tracker/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it("shows the signed-in email and posts a password change", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/auth/password") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          current_password: "correct-horse",
          new_password: "new-horse-1",
        });
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/profile");
    expect(await screen.findByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^profile$/i })).toHaveAttribute(
      "href",
      "/profile",
    );

    await userEvent.type(
      screen.getByLabelText(/current password/i),
      "correct-horse",
    );
    await userEvent.type(
      screen.getByLabelText(/^new password$/i),
      "new-horse-1",
    );
    await userEvent.type(
      screen.getByLabelText(/confirm new password/i),
      "new-horse-1",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /update password/i }),
    );
    expect(await screen.findByText("Password updated.")).toBeInTheDocument();
    expect(screen.getByLabelText(/current password/i)).toHaveValue("");
    expect(screen.getByLabelText(/^new password$/i)).toHaveValue("");
    expect(screen.getByLabelText(/confirm new password/i)).toHaveValue("");
  });

  it("does not call the API when confirm does not match", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    renderAt("/profile");
    await screen.findByText("owner@example.com");
    await userEvent.type(
      screen.getByLabelText(/current password/i),
      "correct-horse",
    );
    await userEvent.type(
      screen.getByLabelText(/^new password$/i),
      "new-horse-1",
    );
    await userEvent.type(
      screen.getByLabelText(/confirm new password/i),
      "other-horse",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /update password/i }),
    );
    expect(
      await screen.findByText("New passwords do not match."),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some((call) =>
          String(call[0]).endsWith("/api/v1/auth/password"),
        ),
    ).toBe(false);
  });

  it("shows the API message when the current password is wrong", async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(200, owner);
      }
      if (url.endsWith("/api/v1/auth/password") && init?.method === "POST") {
        return jsonResponse(401, {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Current password is incorrect.",
          },
        });
      }
      if (url.endsWith("/api/v1/reminders")) {
        return jsonResponse(200, { items: [], unread_count: 0 });
      }
      throw new Error(`unexpected fetch ${url} ${init?.method}`);
    });

    renderAt("/profile");
    await screen.findByText("owner@example.com");
    await userEvent.type(
      screen.getByLabelText(/current password/i),
      "wrong-password",
    );
    await userEvent.type(
      screen.getByLabelText(/^new password$/i),
      "new-horse-1",
    );
    await userEvent.type(
      screen.getByLabelText(/confirm new password/i),
      "new-horse-1",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /update password/i }),
    );
    expect(
      await screen.findByText("Current password is incorrect."),
    ).toBeInTheDocument();
  });
});
