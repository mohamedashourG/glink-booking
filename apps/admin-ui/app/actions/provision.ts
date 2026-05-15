"use server";

import { adminApi, type ApiError, type ProvisionResponse, type BatchResultRow } from "@/lib/api";
import { getSessionToken } from "@/lib/server-session";

export type SingleResult =
  | { ok: true; data: ProvisionResponse }
  | { ok: false; error: string };

export async function provisionSingleAction(_prev: SingleResult | undefined, formData: FormData): Promise<SingleResult> {
  const token = await getSessionToken();
  if (!token) return { ok: false, error: "Not authenticated. Refresh and sign in again." };
  const calendly = String(formData.get("calendly_url") ?? "").trim();
  const body = {
    full_name: String(formData.get("full_name") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim(),
    slug: String(formData.get("slug") ?? "").trim(),
    timezone: String(formData.get("timezone") ?? "America/New_York").trim() || "America/New_York",
    work_start: String(formData.get("work_start") ?? "09:00").trim() || "09:00",
    work_end: String(formData.get("work_end") ?? "18:00").trim() || "18:00",
    calendly_url: calendly || null,
  };
  if (!body.full_name || !body.email || !body.slug) {
    return { ok: false, error: "Name, email, and slug are required." };
  }
  try {
    const data = await adminApi.provisionSingle(token, body);
    return { ok: true, data };
  } catch (err) {
    const e = err as ApiError;
    const detail = typeof e.detail === "string"
      ? e.detail
      : (e.detail as { message?: string } | null)?.message || JSON.stringify(e.detail);
    return { ok: false, error: `Provisioning failed (HTTP ${e.status}): ${detail}` };
  }
}

export type BatchResult = { ok: true; results: BatchResultRow[] } | { ok: false; error: string };

export async function provisionBatchAction(_prev: BatchResult | undefined, formData: FormData): Promise<BatchResult> {
  const token = await getSessionToken();
  if (!token) return { ok: false, error: "Not authenticated. Refresh and sign in again." };
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Choose a CSV file." };
  }
  try {
    const { results } = await adminApi.provisionBatch(token, file);
    return { ok: true, results };
  } catch (err) {
    const e = err as ApiError;
    const detail = typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail);
    return { ok: false, error: `Batch failed (HTTP ${e.status}): ${detail}` };
  }
}
