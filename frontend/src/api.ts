export type User = {
  id: string;
  email: string;
  created_at: string;
};

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  const data = (await response.json()) as T & ErrorBody;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data.error?.code ?? "ERROR",
      data.error?.message ?? "Something went wrong.",
    );
  }
  return data;
}

export function getMe(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

export function login(email: string, password: string): Promise<User> {
  return request<User>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(email: string, password: string): Promise<User> {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}
