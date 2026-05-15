"use client";

import Link from "next/link";
import { useActionState } from "react";
import { provisionSingleAction, type SingleResult } from "@/app/actions/provision";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";

export function NewClientForm() {
  const [state, action, pending] = useActionState<SingleResult | undefined, FormData>(provisionSingleAction, undefined);

  if (state?.ok) {
    const r = state.data.record;
    return (
      <div className="space-y-4">
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4">
          <p className="text-sm text-emerald-900 font-medium">
            {state.data.created ? `✓ ${r.email} created.` : `✓ ${r.email} updated.`}
          </p>
        </div>
        <Field label="Booking link">
          <div className="flex items-center gap-2">
            <a href={r.booking_link} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{r.booking_link}</a>
            <CopyButton value={r.booking_link} />
          </div>
        </Field>
        <Field label="First-login password">
          <Reveal value={r.password} label="Reveal" />
        </Field>
        <Field label="Slug"><code className="font-mono text-sm">{r.slug}</code></Field>
        <div className="pt-2 flex gap-2">
          <Link href={`/clients/${encodeURIComponent(r.slug)}`} className="px-3 py-2 text-sm rounded border border-slate-300 bg-white hover:bg-slate-100">
            View detail
          </Link>
          <Link href="/clients/new" className="px-3 py-2 text-sm rounded bg-slate-900 text-white hover:bg-slate-800">
            Provision another
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form action={action} className="space-y-4">
      <Row id="full_name" label="Full name" placeholder="Acme Inc" required />
      <Row id="email" label="Email" type="email" placeholder="founder@acme.com" required />
      <Row id="slug" label="Slug" placeholder="acme" required hint="Becomes the cal.diy username and the booking-link path." />
      <Row id="timezone" label="Timezone" defaultValue="America/New_York" hint="IANA tz, e.g. Europe/Berlin." />
      <div className="grid grid-cols-2 gap-3">
        <Row id="work_start" label="Work start" defaultValue="09:00" hint="HH:MM in client's tz." />
        <Row id="work_end" label="Work end" defaultValue="18:00" hint="HH:MM in client's tz." />
      </div>
      <Row id="calendly_url" label="Calendly URL (optional)" placeholder="https://calendly.com/.../30min" hint="Used by the outage fallback page." />
      {state && !state.ok && (
        <p className="text-sm text-red-600" role="alert">{state.error}</p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 hover:bg-slate-800"
      >
        {pending ? "Provisioning…" : "Provision"}
      </button>
    </form>
  );
}

function Row({ id, label, hint, ...inputProps }: {
  id: string; label: string; hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        id={id}
        name={id}
        {...inputProps}
        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
      />
      {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-4 items-center">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm">{children}</div>
    </div>
  );
}
