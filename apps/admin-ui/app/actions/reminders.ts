"use server";

import { revalidatePath } from "next/cache";
import {
  adminApi,
  type ApiError,
  type ReminderConfig,
  type ReminderRole,
} from "@/lib/api";
import { getSessionToken } from "@/lib/server-session";

export type SetReminderConfigResult =
  | { ok: true; config: ReminderConfig }
  | { ok: false; error: string };

/** Server action used by the Reminders editor on the client detail page.
 *  Keeps the JWT off the client and gives us a single place to invalidate
 *  the detail-page cache after a successful save. */
export async function setReminderConfigAction(
  slug: string,
  body: { offsets_min: number[]; recipients: ReminderRole[] },
): Promise<SetReminderConfigResult> {
  const token = await getSessionToken();
  if (!token) return { ok: false, error: "Not authenticated. Refresh and sign in again." };
  if (!slug) return { ok: false, error: "Slug missing." };
  try {
    const { config } = await adminApi.setReminderConfig(slug, token, body);
    // Force the detail page to re-fetch on next render so the new config
    // (and the freshly-stored updated_at) shows up without a hard refresh.
    revalidatePath(`/clients/${slug}`);
    return { ok: true, config };
  } catch (err) {
    const e = err as ApiError;
    const detail =
      typeof e.detail === "string"
        ? e.detail
        : (e.detail as { message?: string } | null)?.message || JSON.stringify(e.detail);
    return { ok: false, error: `Save failed (HTTP ${e.status}): ${detail}` };
  }
}
