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

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  return request<void>("/api/v1/auth/password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
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
  policy_id: string | null;
};

export type DocumentList = {
  items: DocumentJob[];
};

export type LinkSuggestion = {
  policy_id: string;
  label: string;
};

export type Policy = ExtractedPolicy & {
  id: string;
  user_id: string;
  source_document_id: string;
  created_at: string;
  updated_at: string;
  property_ids: string[];
  series_id?: string | null;
  previous_premium?: string | null;
  yoy_change_pct?: number | null;
  yoy_flagged?: boolean;
  link_suggestions?: LinkSuggestion[];
};

export type PolicyHistoryPoint = {
  year: number;
  premium: string | null;
  policy_id: string;
};

export type PolicyHistory = {
  items: PolicyHistoryPoint[];
};

export type PolicyList = {
  items: Policy[];
};

export type Property = {
  id: string;
  user_id: string;
  label: string;
  address: string | null;
  stated_value: string | null;
  created_at: string;
  updated_at: string;
  policy_ids: string[];
};

export type PropertyList = {
  items: Property[];
};

export type PropertyWrite = {
  label: string;
  address?: string | null;
  stated_value?: string | null;
};

export type PolicyWrite = ExtractedPolicy & {
  property_ids: string[];
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

export function listPolicies(): Promise<PolicyList> {
  return request<PolicyList>("/api/v1/policies");
}

export function getPolicy(id: string): Promise<Policy> {
  return request<Policy>(`/api/v1/policies/${id}`);
}

export function getPolicyHistory(id: string): Promise<PolicyHistory> {
  return request<PolicyHistory>(`/api/v1/policies/${id}/history`);
}

export function linkPolicy(id: string, peerPolicyId: string): Promise<Policy> {
  return request<Policy>(`/api/v1/policies/${id}/link`, {
    method: "POST",
    body: JSON.stringify({ peer_policy_id: peerPolicyId }),
  });
}

export function unlinkPolicy(id: string): Promise<Policy> {
  return request<Policy>(`/api/v1/policies/${id}/link`, { method: "DELETE" });
}

export function updatePolicy(id: string, body: PolicyWrite): Promise<Policy> {
  return request<Policy>(`/api/v1/policies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deletePolicy(id: string): Promise<void> {
  return request<void>(`/api/v1/policies/${id}`, { method: "DELETE" });
}

export function listProperties(): Promise<PropertyList> {
  return request<PropertyList>("/api/v1/properties");
}

export function getProperty(id: string): Promise<Property> {
  return request<Property>(`/api/v1/properties/${id}`);
}

export function createProperty(body: PropertyWrite): Promise<Property> {
  return request<Property>("/api/v1/properties", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProperty(
  id: string,
  body: Partial<PropertyWrite>,
): Promise<Property> {
  return request<Property>(`/api/v1/properties/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteProperty(id: string): Promise<void> {
  return request<void>(`/api/v1/properties/${id}`, { method: "DELETE" });
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

export type Reminder = {
  id: string;
  policy_id: string;
  threshold_days: number;
  renewal_date: string;
  read_at: string | null;
  named_insured: string | null;
  coverage_type: string | null;
};

export type ReminderList = {
  items: Reminder[];
  unread_count: number;
};

export function listReminders(): Promise<ReminderList> {
  return request<ReminderList>("/api/v1/reminders");
}

export function markReminderRead(id: string): Promise<Reminder> {
  return request<Reminder>(`/api/v1/reminders/${id}/read`, { method: "POST" });
}

export function markReminderUnread(id: string): Promise<Reminder> {
  return request<Reminder>(`/api/v1/reminders/${id}/unread`, {
    method: "POST",
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
