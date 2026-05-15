// Server-side admin-api client. Read SESSION_COOKIE from the request
// (via Next's `cookies()` helper) and forward it as Bearer to admin-api.
// Never imported from a client component — always invoked from server
// components, server actions, or middleware.

const ADMIN_API_BASE = process.env.ADMIN_API_BASE || "http://localhost:8002";
export const SESSION_COOKIE = process.env.ADMIN_UI_COOKIE_NAME || "glink_admin_ui_session";

export type ListedClient = {
  slug: string;
  full_name: string;
  email: string;
  calendly_url: string | null;
  webhook_coverage: "platform" | "per-user" | "none";
};

export type ProvisionedRecord = {
  email: string;
  slug: string;
  full_name: string;
  timezone: string;
  password: string;
  cal_user_id: number;
  schedule_id: number;
  event_type_id: number;
  event_type_slug: string;
  booking_link: string;
  work_start: string;
  work_end: string;
  webhook_id: string | null;
  calendly_url: string | null;
};

export type ClientDetail = {
  record: ProvisionedRecord;
  webhook_coverage: "platform" | "per-user" | "none";
};

export type ProvisionResponse = {
  ok: true;
  created: boolean;
  record: ProvisionedRecord;
};

export type BatchResultRow =
  | { row: number; ok: true; email: string; slug: string; created: boolean; record: ProvisionedRecord }
  | { row: number; ok: false; email?: string; step: string; message: string };

export type ApiError = { detail: unknown; status: number };

async function call<T>(path: string, init: RequestInit = {}, token: string | null): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (init.body && !(init.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${ADMIN_API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail ?? data ?? res.statusText;
    const err: ApiError = { detail, status: res.status };
    throw err;
  }
  return data as T;
}

export type LoginResponse = {
  email: string;
  role: string;
  name: string | null;
  inactive_admin_reason: string | null;
  token: string;
  expires_at: number;
};

export const adminApi = {
  login: (email: string, password: string) =>
    call<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, null),

  me: (token: string) => call<{ email: string; role: string; expires_at: number }>("/auth/me", {}, token),

  listClients: (token: string) => call<{ clients: ListedClient[] }>("/clients", {}, token),

  getClient: (slug: string, token: string) => call<ClientDetail>(`/clients/${encodeURIComponent(slug)}`, {}, token),

  provisionSingle: (token: string, body: {
    full_name: string;
    email: string;
    slug: string;
    timezone?: string;
    work_start?: string;
    work_end?: string;
    calendly_url?: string | null;
  }) => call<ProvisionResponse>("/provision/single", { method: "POST", body: JSON.stringify(body) }, token),

  provisionBatch: (token: string, csv: File) => {
    const fd = new FormData();
    fd.append("file", csv);
    return call<{ results: BatchResultRow[] }>("/provision/batch", { method: "POST", body: fd }, token);
  },
};
