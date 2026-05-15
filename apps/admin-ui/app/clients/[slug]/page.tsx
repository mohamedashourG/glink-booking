import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  Calendar,
  Clock,
  Globe,
  KeyRound,
  Link as LinkIcon,
  Settings2,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { adminApi, type ApiError } from "@/lib/api";
import { requireToken } from "@/lib/server-session";
import { AppShell } from "@/components/AppShell";
import { Avatar } from "@/components/Avatar";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";
import { CoverageBadge } from "@/components/CoverageBadge";

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
    <AppShell adminEmail={email}>
      <main className="mx-auto max-w-5xl px-8 py-8 animate-fade-in">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          All clients
        </Link>

        {/* Hero -------------------------------------------------------- */}
        <div className="card card-pad mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div className="flex items-center gap-4 min-w-0">
            <Avatar seed={record.full_name || record.email} size="xl" />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold text-ink-900 tracking-tight truncate">{record.full_name}</h1>
              <p className="text-sm text-ink-500 truncate">{record.email}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <CoverageBadge value={webhook_coverage} />
                <span className="badge-neutral">
                  <Globe className="h-3 w-3" /> {record.timezone}
                </span>
                <span className="chip-mono">{record.slug}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <CopyButton value={record.booking_link} label="Copy link" />
            <a
              href={record.booking_link}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary"
            >
              <LinkIcon className="h-4 w-4" />
              Open booking page
              <ArrowUpRight className="h-3.5 w-3.5 opacity-80" />
            </a>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column ----------------------------------------------- */}
          <div className="lg:col-span-2 space-y-6">
            <SectionCard Icon={LinkIcon} title="Booking link" eyebrow="Public URL">
              <div className="flex items-center gap-2 rounded-lg border border-ink-200 bg-ink-50/60 px-3 py-2.5">
                <span className="flex-1 truncate text-sm font-mono text-ink-800">{record.booking_link}</span>
                <CopyButton value={record.booking_link} variant="ghost" />
              </div>
            </SectionCard>

            <SectionCard Icon={KeyRound} title="First-login password" eyebrow="Sensitive">
              <Reveal value={record.password} />
              <p className="hint">
                Share with the client through a secure channel. They&apos;ll set their own password on first login.
              </p>
            </SectionCard>

            <SectionCard Icon={Settings2} title="Configuration" eyebrow="Schedule policy">
              <DescList
                items={[
                  { label: "Timezone", Icon: Globe, value: <code className="chip-mono">{record.timezone}</code> },
                  {
                    label: "Working hours",
                    Icon: Clock,
                    value: <code className="chip-mono">{record.work_start} – {record.work_end}</code>,
                  },
                  {
                    label: "Calendly fallback",
                    Icon: Calendar,
                    value: record.calendly_url ? (
                      <a
                        href={record.calendly_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-brand-700 hover:text-brand-800 break-all"
                      >
                        {record.calendly_url}
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-ink-400 italic">none configured</span>
                    ),
                  },
                ]}
              />
            </SectionCard>
          </div>

          {/* Right column ---------------------------------------------- */}
          <div className="space-y-6">
            <SectionCard Icon={ShieldCheck} title="Webhook" eyebrow="Coverage">
              <CoverageBadge value={webhook_coverage} />
              {record.webhook_id && (
                <p className="mt-3 text-xs text-ink-500">
                  Per-user webhook id:
                  <br />
                  <code className="chip-mono mt-1 inline-block break-all">{record.webhook_id}</code>
                </p>
              )}
              {webhook_coverage === "platform" && (
                <p className="mt-3 text-xs text-ink-500">
                  Bookings flow through the platform-wide webhook into the receiver — no per-client setup required.
                </p>
              )}
            </SectionCard>

            <SectionCard Icon={TerminalSquare} title="cal.diy IDs" eyebrow="Internal">
              <DescList
                dense
                items={[
                  { label: "user_id", value: <code className="chip-mono">{record.cal_user_id}</code> },
                  { label: "schedule_id", value: <code className="chip-mono">{record.schedule_id}</code> },
                  { label: "event_type_id", value: <code className="chip-mono">{record.event_type_id}</code> },
                  { label: "event_type_slug", value: <code className="chip-mono">{record.event_type_slug}</code> },
                ]}
              />
            </SectionCard>
          </div>
        </div>
      </main>
    </AppShell>
  );
}

function SectionCard({
  Icon,
  title,
  eyebrow,
  children,
}: {
  Icon: typeof LinkIcon;
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card card-pad">
      <header className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-brand-100 text-brand-700 p-2">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
          </div>
        </div>
      </header>
      <div>{children}</div>
    </section>
  );
}

function DescList({
  items,
  dense = false,
}: {
  items: { label: string; Icon?: typeof LinkIcon; value: React.ReactNode }[];
  dense?: boolean;
}) {
  return (
    <dl className={`divide-y divide-ink-100 ${dense ? "" : ""}`}>
      {items.map(({ label, Icon, value }, i) => (
        <div key={label} className={`grid grid-cols-[110px_1fr] items-center gap-3 ${i === 0 ? "pb-2.5" : "py-2.5"} ${i === items.length - 1 ? "pb-0 pt-2.5" : ""}`}>
          <dt className="flex items-center gap-2 text-xs font-medium text-ink-500">
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {label}
          </dt>
          <dd className="text-sm text-ink-800 min-w-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
