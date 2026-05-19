// Client-portal iframe target.
//
// Loaded INSIDE cal.diy via <iframe src=".../portal/embed?token=...">.
// Flow:
//   1. Read the one-time JWT from `?token=`.
//   2. POST it to admin-api /portal/exchange — returns a session token.
//   3. Render the ReminderEditor wired to that session token; save calls
//      admin-api directly (no Server Action — Server Actions would need
//      a cookie which we deliberately avoid in cross-origin iframes).
//
// This page intentionally has no AppShell / sidebar — it's the iframe
// content, so the chrome lives in cal.diy.
import { PortalEmbed } from "./PortalEmbed";

export const dynamic = "force-dynamic";

// Allow cal.diy to frame this page. Without this, the browser refuses
// to render the iframe contents and the operator sees a blank tab.
// We use frame-ancestors (CSP) — modern, replaces X-Frame-Options.
// CAL_PUBLIC_BASE is the cal.diy origin; localhost dev + Fly prod both
// covered when the env var points to the right thing.
export async function generateMetadata() {
  return { title: "Reminders · cal.diy" };
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  // Pass the admin-api origin in so the client-side fetch knows where to
  // POST the exchange. We can't use a relative URL here — the iframe
  // doesn't share an origin with admin-api in production.
  const adminApiBase = process.env.ADMIN_API_BASE || "http://localhost:8002";
  return <PortalEmbed initialToken={token ?? null} adminApiBase={adminApiBase} />;
}
