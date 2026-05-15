import Link from "next/link";
import { ArrowLeft, Sparkles, Clock, ShieldCheck, CalendarHeart } from "lucide-react";
import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { NewClientForm } from "./NewClientForm";

export default async function NewClientPage() {
  const { email } = await requireToken();
  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-5xl px-6 py-8 animate-fade-in">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          All clients
        </Link>

        <div className="mt-4 flex items-end justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-[1.65rem] font-semibold text-ink-900 tracking-tight">Add a client</h1>
            <p className="mt-1 text-sm text-ink-500">
              We&apos;ll create the cal.diy login, set up the standard 30-minute event type, and surface the booking link.
            </p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6">
          <div className="card card-pad">
            <NewClientForm />
          </div>

          <aside className="space-y-3">
            <h2 className="eyebrow px-1">What happens next</h2>
            <Pip
              Icon={Sparkles}
              title="Cal.diy account is created"
              body="A new login is provisioned with the email you provide. We capture a one-time first-login password."
            />
            <Pip
              Icon={Clock}
              title="Schedule is configured"
              body="Working hours apply to the client's timezone. Buffers of 15 min before/after, 4 h minimum notice, 60-day window."
            />
            <Pip
              Icon={CalendarHeart}
              title="30-min event type"
              body="Standard policy: max 5 bookings/day, name + email + 'What would you like to discuss?'."
            />
            <Pip
              Icon={ShieldCheck}
              title="Webhook coverage"
              body="The platform-wide webhook covers the new client automatically — no extra setup."
            />
          </aside>
        </div>
      </main>
    </>
  );
}

function Pip({ Icon, title, body }: { Icon: typeof Sparkles; title: string; body: string }) {
  return (
    <div className="card p-4 flex gap-3 items-start">
      <div className="rounded-lg bg-brand-50 text-brand-600 p-2 shrink-0">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink-900">{title}</div>
        <p className="text-xs text-ink-500 mt-0.5 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}
