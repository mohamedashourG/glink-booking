import Link from "next/link";
import { notFound } from "next/navigation";
import { adminApi, type ApiError } from "@/lib/api";
import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";

const COVERAGE_BADGE: Record<string, string> = {
  platform: "bg-emerald-100 text-emerald-800",
  "per-user": "bg-amber-100 text-amber-800",
  none: "bg-red-100 text-red-800",
};

export default async function ClientDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { token, email } = await requireToken();
  let detail;
  try {
    detail = await adminApi.getClient(slug, token);
  } catch (err) {
    if ((err as ApiError).status === 404) notFound();
    throw err;
  }
  const { record, webhook_coverage } = detail;

  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Link href="/" className="text-sm text-slate-500 hover:underline">← All clients</Link>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">{record.full_name}</h1>
        <p className="text-sm text-slate-500">{record.email}</p>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <Field label="Slug"><code className="font-mono">{record.slug}</code></Field>
          <Field label="Booking link">
            <div className="flex items-center gap-2">
              <a href={record.booking_link} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{record.booking_link}</a>
              <CopyButton value={record.booking_link} />
            </div>
          </Field>
          <Field label="First-login password">
            <Reveal value={record.password} />
          </Field>
          <Field label="Webhook coverage">
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${COVERAGE_BADGE[webhook_coverage] ?? "bg-slate-100 text-slate-700"}`}>
              {webhook_coverage}
            </span>
            {record.webhook_id && (
              <span className="ml-2 text-xs text-slate-500 font-mono">{record.webhook_id}</span>
            )}
          </Field>
        </section>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Configuration</h2>
          <Field label="Timezone"><code className="font-mono">{record.timezone}</code></Field>
          <Field label="Working hours"><code className="font-mono">{record.work_start} – {record.work_end}</code></Field>
          <Field label="Calendly fallback">
            {record.calendly_url ? (
              <a href={record.calendly_url} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline break-all">
                {record.calendly_url}
              </a>
            ) : <span className="text-slate-400">none</span>}
          </Field>
        </section>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">cal.diy ids</h2>
          <Field label="cal_user_id"><code className="font-mono">{record.cal_user_id}</code></Field>
          <Field label="schedule_id"><code className="font-mono">{record.schedule_id}</code></Field>
          <Field label="event_type_id"><code className="font-mono">{record.event_type_id}</code></Field>
          <Field label="event_type_slug"><code className="font-mono">{record.event_type_slug}</code></Field>
        </section>
      </main>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-4 items-center">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm">{children}</div>
    </div>
  );
}
