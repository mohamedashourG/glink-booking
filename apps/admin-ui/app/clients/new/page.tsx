import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { requireToken } from "@/lib/server-session";
import { adminApi } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { NewClientForm } from "./NewClientForm";

export default async function NewClientPage() {
  const { token, email } = await requireToken();
  // Pre-load existing slugs so the form can warn inline before submit,
  // instead of bouncing back from admin-api with a signup-conflict error.
  const { clients } = await adminApi.listClients(token);
  const existingSlugs = clients.map((c) => c.slug.toLowerCase());
  return (
    <AppShell adminEmail={email}>
      <main className="mx-auto max-w-3xl px-8 py-10 animate-fade-in">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          All clients
        </Link>

        <header className="mt-6 mb-8">
          <h1 className="text-2xl font-semibold text-ink-900 tracking-tight">Add a client</h1>
          <p className="mt-1.5 text-sm text-ink-500">
            We&apos;ll create the bookings@glnkco.com login, set up the standard 30-minute event type, and surface the booking link.
          </p>
        </header>

        <NewClientForm existingSlugs={existingSlugs} />

        {/* Slim, inline footer instead of a sidebar. Same information as
            the previous 'What happens next' cards, but tucked under the
            form so the eye isn't competing with it during data entry. */}
        <footer className="mt-12 pt-6 border-t border-ink-100">
          <div className="text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-ink-500 mb-3">
            What happens next
          </div>
          <ul className="space-y-2 text-sm text-ink-600">
            <NextStep n={1}>
              <strong className="text-ink-900">Cal.diy account is created</strong> with the email you provide.
              We capture a one-time first-login password.
            </NextStep>
            <NextStep n={2}>
              <strong className="text-ink-900">Schedule is configured</strong> in the client&apos;s timezone with 15-min buffers,
              4-hour minimum notice, and a 60-day window.
            </NextStep>
            <NextStep n={3}>
              <strong className="text-ink-900">30-minute event type</strong> with the standard policy
              (max 5 bookings/day, name + email + &ldquo;What would you like to discuss?&rdquo;).
            </NextStep>
            <NextStep n={4}>
              <strong className="text-ink-900">Webhook coverage</strong> is automatic — the platform-wide webhook covers the new client.
            </NextStep>
          </ul>
        </footer>
      </main>
    </AppShell>
  );
}

function NextStep({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="text-ink-400 tabular-nums w-4 shrink-0 mt-0.5">{n}.</span>
      <span>{children}</span>
    </li>
  );
}
