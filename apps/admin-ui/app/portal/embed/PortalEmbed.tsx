"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReminderConfig, ReminderRole } from "@/lib/api";
import { ReminderEditor } from "@/app/clients/[slug]/ReminderEditor";

/**
 * Handles the JWT handshake then renders the Reminders editor for the
 * authenticated slug. Errors are surfaced inline (no redirect — the
 * iframe has nowhere to redirect TO).
 *
 * Why this is a separate client component (not a server component):
 * - The exchange call has to happen in the browser, not on the
 *   admin-ui server, because admin-api is reached over the public
 *   network from the operator's browser (matches existing pattern).
 * - We store the session token in memory only — never in a cookie or
 *   localStorage — so closing the iframe clears it.
 */

type SessionState =
  | { kind: "idle" }
  | { kind: "exchanging" }
  | { kind: "ready"; sessionToken: string; slug: string; email: string; config: ReminderConfig }
  | { kind: "error"; message: string };

export function PortalEmbed({
  initialToken,
  adminApiBase,
}: {
  initialToken: string | null;
  adminApiBase: string;
}) {
  const [state, setState] = useState<SessionState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!initialToken) {
        setState({ kind: "error", message: "Missing access token. Re-open this tab from cal.diy." });
        return;
      }
      setState({ kind: "exchanging" });
      try {
        // 1) Exchange the cal.diy-issued JWT for a portal session token.
        const exchangeRes = await fetch(`${adminApiBase}/portal/exchange`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cal_token: initialToken }),
        });
        if (!exchangeRes.ok) {
          const body = await exchangeRes.text();
          throw new Error(`Could not authenticate (HTTP ${exchangeRes.status}): ${body || exchangeRes.statusText}`);
        }
        const { session, slug, email } = (await exchangeRes.json()) as {
          session: string;
          slug: string;
          email: string;
        };

        // 2) Fetch the current reminder config so the editor pre-populates.
        const cfgRes = await fetch(
          `${adminApiBase}/clients/${encodeURIComponent(slug)}/reminders`,
          { headers: { Authorization: `Bearer ${session}` } },
        );
        if (!cfgRes.ok) {
          const body = await cfgRes.text();
          throw new Error(`Could not load reminder config (HTTP ${cfgRes.status}): ${body || cfgRes.statusText}`);
        }
        const { config } = (await cfgRes.json()) as { config: ReminderConfig };

        if (!cancelled) {
          setState({ kind: "ready", sessionToken: session, slug, email, config });
        }
      } catch (err) {
        if (!cancelled) {
          setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [initialToken, adminApiBase]);

  if (state.kind === "exchanging" || state.kind === "idle") {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <div className="flex items-center gap-3 text-ink-500 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading reminders…
        </div>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md flex items-start gap-3 text-sm">
          <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <h1 className="font-medium text-ink-900">Couldn&apos;t load reminders</h1>
            <p className="text-ink-500 mt-1">{state.message}</p>
          </div>
        </div>
      </main>
    );
  }

  // Narrow once, then close over the locals — TypeScript can't narrow
  // a closure across the discriminated-union check otherwise.
  const { sessionToken, slug, email, config } = state;

  async function save(body: { offsets_min: number[]; recipients: ReminderRole[] }) {
    const res = await fetch(
      `${adminApiBase}/clients/${encodeURIComponent(slug)}/reminders`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      },
    );
    if (!res.ok) {
      const detail = await res.text();
      return { ok: false as const, error: `Save failed (HTTP ${res.status}): ${detail}` };
    }
    const { config: returned } = (await res.json()) as { config: ReminderConfig };
    return { ok: true as const, config: returned };
  }

  return (
    <main className="min-h-screen p-6 sm:p-8 bg-white">
      <header className="mb-6">
        <h1 className="text-base font-medium text-ink-900">Meeting reminders</h1>
        <p className="text-xs text-ink-500 mt-1">
          Signed in as {email} · slug <code className="chip-mono">{slug}</code>
        </p>
      </header>
      <ReminderEditor slug={slug} initial={config} saveOverride={save} />
    </main>
  );
}
