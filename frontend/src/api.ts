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

export type Deductible = {
  peril: string | null;
  amount: string | null;
};

export type Location = {
  label: string | null;
  address: string | null;
};

export type FieldConfidence = {
  policy_number: number;
  named_insured: number;
  broker: number;
  effective_date: number;
  renewal_date: number;
  term_premium: number;
  policy_fee: number;
  total_premium: number;
  limit_of_insurance: number;
  coverage_type: number;
  carriers: number;
  deductibles: number;
  locations: number;
};

export type ExtractedPolicy = {
  policy_number: string | null;
  named_insured: string | null;
  broker: string | null;
  effective_date: string | null;
  renewal_date: string | null;
  term_premium: string | null;
  policy_fee: string | null;
  total_premium: string | null;
  limit_of_insurance: string | null;
  coverage_type: string | null;
  carriers: string[];
  deductibles: Deductible[];
  locations: Location[];
  confidence: FieldConfidence;
};

export type DocumentJob = {
  id: string;
  user_id: string;
  original_filename: string;
  content_type: string;
  byte_size: number;
  status: "pending" | "processing" | "completed" | "failed" | "reviewed";
  extracted: ExtractedPolicy | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentList = {
  items: DocumentJob[];
};

async function readError(response: Response): Promise<ApiError> {
  const data = (await response.json()) as ErrorBody;
  return new ApiError(
    response.status,
    data.error?.code ?? "ERROR",
    data.error?.message ?? "Something went wrong.",
  );
}

export function listDocuments(): Promise<DocumentList> {
  return request<DocumentList>("/api/v1/documents");
}

export function getDocument(id: string): Promise<DocumentJob> {
  return request<DocumentJob>(`/api/v1/documents/${id}`);
}

export function confirmDocument(
  id: string,
  extracted: ExtractedPolicy,
): Promise<DocumentJob> {
  return request<DocumentJob>(`/api/v1/documents/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify(extracted),
  });
}

export async function uploadDocuments(files: File[]): Promise<DocumentList> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file);
  }
  const response = await fetch("/api/v1/documents", {
    method: "POST",
    credentials: "include",
    body,
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as DocumentList;
}
