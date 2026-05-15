"use client";

import Link from "next/link";
import { useActionState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Globe,
  Loader2,
  Mail,
  Plus,
  Tag,
  User,
  Calendar,
} from "lucide-react";
import { provisionSingleAction, type SingleResult } from "@/app/actions/provision";
import { Avatar } from "@/components/Avatar";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";

export function NewClientForm() {
  const [state, action, pending] = useActionState<SingleResult | undefined, FormData>(provisionSingleAction, undefined);

  if (state?.ok) {
    const r = state.data.record;
    return (
      <div className="animate-fade-in">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-3">
          <div className="rounded-full bg-emerald-100 p-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-700" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-emerald-900">
              {state.data.created ? "Client provisioned" : "Client updated"}
            </div>
            <p className="text-xs text-emerald-800/80 mt-0.5">
              {r.email} is ready. Share the booking link and the first-login password through a secure channel.
            </p>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Avatar seed={r.full_name || r.email} size="lg" />
          <div className="min-w-0">
            <div className="font-medium text-ink-900 truncate">{r.full_name}</div>
            <div className="text-xs text-ink-500 truncate">{r.email}</div>
          </div>
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <div className="eyebrow mb-2">Booking link</div>
            <div className="flex items-center gap-2 rounded-lg border border-ink-200 bg-ink-50/60 px-3 py-2.5">
              <a
                href={r.booking_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 truncate text-sm font-mono text-brand-700 hover:text-brand-800"
              >
                {r.booking_link}
              </a>
              <CopyButton value={r.booking_link} variant="ghost" />
            </div>
          </div>

          <div>
            <div className="eyebrow mb-2">First-login password</div>
            <Reveal value={r.password} />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          <Link href={`/clients/${encodeURIComponent(r.slug)}`} className="btn-secondary">
            View details
          </Link>
          <Link href="/clients/new" className="btn-primary">
            <Plus className="h-4 w-4" />
            Add another
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form action={action} className="space-y-6">
      <FieldGroup
        title="Identity"
        description="The client's name + email become the cal.diy login. The slug becomes their booking-link path."
      >
        <Field id="full_name" label="Full name" Icon={User} placeholder="Acme Inc" required />
        <Field id="email" label="Email" type="email" Icon={Mail} placeholder="founder@acme.com" required />
        <Field
          id="slug"
          label="Slug"
          Icon={Tag}
          placeholder="acme"
          required
          hint="Becomes the cal.diy username and the booking-link path."
        />
      </FieldGroup>

      <FieldGroup
        title="Schedule"
        description="Working hours apply to the client's timezone. Defaults are Mon–Fri 09:00–18:00."
      >
        <Field id="timezone" label="Timezone" Icon={Globe} defaultValue="America/New_York" hint="IANA tz, e.g. Europe/Berlin." />
        <div className="grid grid-cols-2 gap-3">
          <Field id="work_start" label="Work start" Icon={Clock} defaultValue="09:00" hint="HH:MM in client's tz." />
          <Field id="work_end" label="Work end" Icon={Clock} defaultValue="18:00" />
        </div>
      </FieldGroup>

      <FieldGroup
        title="Fallback"
        description="Used by the outage page when cal.diy is unreachable. Optional."
      >
        <Field
          id="calendly_url"
          label="Calendly URL"
          Icon={Calendar}
          placeholder="https://calendly.com/.../30min"
        />
      </FieldGroup>

      {state && !state.ok && (
        <div role="alert" className="flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2.5 text-sm text-rose-700">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{state.error}</span>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-ink-100 pt-5">
        <Link href="/" className="btn-secondary">Cancel</Link>
        <button type="submit" disabled={pending} className="btn-primary">
          {pending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Provisioning…
            </>
          ) : (
            <>
              Provision client
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}

function FieldGroup({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        <p className="text-xs text-ink-500 mt-0.5">{description}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({
  id,
  label,
  hint,
  Icon,
  ...props
}: {
  id: string;
  label: string;
  hint?: string;
  Icon?: typeof User;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400 pointer-events-none" />}
        <input
          id={id}
          name={id}
          {...props}
          className={`input ${Icon ? "input-with-icon" : ""}`}
        />
      </div>
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}
