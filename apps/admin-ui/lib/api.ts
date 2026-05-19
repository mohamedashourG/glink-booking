// Server-side admin-api client. Read SESSION_COOKIE from the request
// (via Next's `cookies()` helper) and forward it as Bearer to admin-api.
// Never imported from a client component — always invoked from server
// components, server actions, or middleware.

const ADMIN_API_BASE = process.env.ADMIN_API_BASE || "http://localhost:8002";
export const SESSION_COOKIE = process.env.ADMIN_UI_COOKIE_NAME || "glink_admin_ui_session";

export type MeetingCounts = {
  total: number;
  created: number;
  rescheduled: number;
  cancelled: number;
  rejected: number;
  last_at: string | null; // ISO 8601, or null
};

export type ListedClient = {
  slug: string;                         // stored slug from the manifest
  live_username: string | null;         // current cal.diy username (null if pool absent)
  effective_slug: string;               // live_username when present, else stored slug
  drift: boolean;                       // stored slug != live username
  full_name: string;
  email: string;
  calendly_url: string | null;
  webhook_coverage: "platform" | "per-user" | "none";
  meetings: MeetingCounts;
};

export type ReminderRole = "prospect" | "host" | "agency";

export type ReminderConfig = {
  offsets_min: number[];        // sorted desc by admin-api
  recipients: ReminderRole[];
  is_default: boolean;           // true = no per-client row exists; effective config is env-default
  updated_at: string | null;     // ISO 8601 or null
};

export type ReminderStatusCounts = {
  pending: number;
  processing: number;
  sent: number;
  failed: number;
  cancelled: number;
};

export type ListClientsTotals = {
  meetings_total: number;
  meetings_created: number;
  meetings_rescheduled: number;
  meetings_cancelled: number;
  meetings_rejected: number;
  clients_with_drift: number;
  reminders_pending_24h: number;
  reminders_by_status: ReminderStatusCounts;
};

export type BookingRow = {
  cal_booking_uid: string;
  current_event: "BOOKING_CREATED" | "BOOKING_RESCHEDULED" | "BOOKING_CANCELLED" | "BOOKING_REJECTED";
  prospect_name: string | null;
  prospect_email: string | null;
  prospect_company: string | null;
  scheduled_at: string | null; // ISO 8601
  timezone: string | null;
  video_link: string | null;
  received_at: string;         // ISO 8601
  reminders?: ReminderStatusCounts; // present on detail responses; undefined on list rows
};

export type SlugCheck = {
  slug: string;
  valid_format: boolean;
  taken_in_manifest: boolean;
  taken_in_cal: boolean | null; // null = couldn't check (pool absent or query failed)
  available: boolean;            // convenience: format ok AND neither side reports taken
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
  live_username: string | null;
  effective_slug: string;
  drift: boolean;
  webhook_coverage: "platform" | "per-user" | "none";
  meetings: MeetingCounts;
  bookings: BookingRow[];
  reminder_config: ReminderConfig;
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

  listClients: (token: string) =>
    call<{ clients: ListedClient[]; totals: ListClientsTotals }>("/clients", {}, token),

  /** Live slug check against cal.diy + local manifest. Used by the
   *  new-client form for inline pre-submit validation. */
  checkSlug: (slug: string, token: string) =>
    call<SlugCheck>(`/slug-available?slug=${encodeURIComponent(slug)}`, {}, token),

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

  /** Update the per-client reminder policy. Server validates + normalizes;
   *  the returned config is what was actually stored. */
  setReminderConfig: (
    slug: string,
    token: string,
    body: { offsets_min: number[]; recipients: ReminderRole[] },
  ) =>
    call<{ ok: true; slug: string; config: ReminderConfig }>(
      `/clients/${encodeURIComponent(slug)}/reminders`,
      { method: "PUT", body: JSON.stringify(body) },
      token,
    ),
};
