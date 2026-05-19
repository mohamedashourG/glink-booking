import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  Bell,
  CalendarCheck,
  CalendarX,
  Link as LinkIcon,
  RefreshCw,
  Video,
  XCircle,
} from "lucide-react";
import { adminApi, type ApiError, type BookingRow, type MeetingCounts } from "@/lib/api";
import { requireToken } from "@/lib/server-session";
import { AppShell } from "@/components/AppShell";
import { Avatar } from "@/components/Avatar";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";
import { CoverageBadge } from "@/components/CoverageBadge";
import { ReminderEditor } from "./ReminderEditor";

/**
 * Client detail — Linear-style flat layout.
 *
 * Visual rules applied here:
 * - No nested card containers. Sections are separated by whitespace +
 *   a single hairline rule under each heading.
 * - Two columns on lg+: the primary column carries the "doing" content
 *   (booking link, bookings list, reminder editor); the side rail
 *   carries the "knowing" content (coverage, password, IDs).
 * - No input icons. Headings + eyebrows carry the meaning.
 */
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
  const {
    record,
    webhook_coverage,
    live_username,
    effective_slug,
    drift,
    meetings,
    bookings,
    reminder_config,
  } = detail;

  // Rebuild the booking link from the live slug so a rename on cal.diy
  // doesn't leave the operator copying a 404 URL. record.booking_link is
  // still preserved for reference but we don't surface it directly when
  // it's drifted.
  const publicBase = process.env.CAL_PUBLIC_BASE || "http://localhost:3000";
  const liveBookingLink = `${publicBase}/${effective_slug}/30min`;

  return (
    <AppShell adminEmail={email}>
      <main className="mx-auto max-w-6xl px-8 py-10 animate-fade-in">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          All clients
        </Link>

        {drift && (
          // Drift signal stays as an inline notice — important enough to
          // see, low-key enough not to dominate.
          <div className="mt-5 flex items-start gap-2.5 text-sm">
            <RefreshCw className="h-4 w-4 mt-0.5 text-amber-600 shrink-0" />
            <p className="text-ink-700">
              <span className="font-medium text-ink-900">Renamed in cal.diy.</span>{" "}
              Stored slug <code className="chip-mono">{record.slug}</code>{" "}
              · cal.diy now says <code className="chip-mono">{live_username}</code>.
              The link below uses the live name; bookings from before the rename live under the old slug.
            </p>
          </div>
        )}

        {/* Hero — no card, just a horizontal layout with name, identity,
            and the two primary actions. */}
        <section className="mt-8 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4 min-w-0">
            <Avatar seed={record.full_name || record.email} size="xl" />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold text-ink-900 tracking-tight truncate">
                {record.full_name}
              </h1>
              <p className="text-sm text-ink-500 truncate">{record.email}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <code className="chip-mono">{effective_slug}</code>
                <span className="text-xs text-ink-400">·</span>
                <span className="text-xs text-ink-500">{record.timezone}</span>
                <span className="text-xs text-ink-400">·</span>
                <CoverageBadge value={webhook_coverage} />
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <CopyButton value={liveBookingLink} label="Copy link" />
            <a
              href={liveBookingLink}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary"
            >
              <LinkIcon className="h-4 w-4" />
              Open booking page
              <ArrowUpRight className="h-3.5 w-3.5 opacity-80" />
            </a>
          </div>
        </section>

        {/* Status breakdown — tighter chip styling. Zero-count chips are
            visually quiet so the eye lands on real activity. */}
        <StatusBreakdown meetings={meetings} className="mt-10" />

        {/* Two columns from lg up; stacks on smaller. Wide right rail is
            intentionally narrow so the primary content has breathing room. */}
        <div className="mt-14 grid gap-14 lg:grid-cols-[1fr_280px]">
          {/* Primary column */}
          <div className="space-y-12 min-w-0">
            <Section title="Booking link" eyebrow="public url">
              <div className="flex items-center gap-2 rounded-lg border border-ink-200 bg-ink-50/40 px-3 py-2">
                <span className="flex-1 truncate text-sm font-mono text-ink-800">{liveBookingLink}</span>
                <CopyButton value={liveBookingLink} variant="ghost" />
              </div>
              {drift && (
                <p className="hint">
                  Stored link was <code className="chip-mono">{record.booking_link}</code> — overridden by cal.diy rename.
                </p>
              )}
            </Section>

            <Section
              title="Bookings"
              eyebrow={meetings.total === 0 ? "no data yet" : `${meetings.total} total`}
            >
              <BookingsList bookings={bookings} />
            </Section>

            <Section
              title="Reminders"
              eyebrow={
                reminder_config.is_default
                  ? "using defaults"
                  : reminder_config.updated_at
                    ? `saved ${new Date(reminder_config.updated_at).toLocaleString()}`
                    : "custom"
              }
            >
              {/* The editor renders its own padded form. Inside, we pass
                  the live slug so renames write to the right config row. */}
              <ReminderEditor slug={effective_slug} initial={reminder_config} />
            </Section>
          </div>

          {/* Side rail */}
          <aside className="space-y-10 min-w-0">
            <SideSection title="First-login password" eyebrow="sensitive">
              <Reveal value={record.password} />
              <p className="hint">
                Share with the client through a secure channel. They&apos;ll set their own password on first login.
              </p>
            </SideSection>

            <SideSection title="Configuration">
              <DescList
                items={[
                  { label: "Timezone", value: <code className="chip-mono">{record.timezone}</code> },
                  {
                    label: "Hours",
                    value: <code className="chip-mono">{record.work_start} – {record.work_end}</code>,
                  },
                  {
                    label: "Calendly",
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
            </SideSection>

            <SideSection title="Webhook" eyebrow="coverage">
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
                  Platform-wide webhook covers this client. No per-client setup required.
                </p>
              )}
            </SideSection>

            <SideSection title="bookings@glnkco.com IDs" eyebrow="internal">
              <DescList
                dense
                items={[
                  { label: "user", value: <code className="chip-mono">{record.cal_user_id}</code> },
                  { label: "schedule", value: <code className="chip-mono">{record.schedule_id}</code> },
                  { label: "event type", value: <code className="chip-mono">{record.event_type_id}</code> },
                  { label: "event slug", value: <code className="chip-mono">{record.event_type_slug}</code> },
                ]}
              />
            </SideSection>
          </aside>
        </div>
      </main>
    </AppShell>
  );
}

/* ── Layout primitives ──────────────────────────────────────────────────── */

function Section({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="flex items-baseline gap-3 pb-3 mb-4 border-b border-ink-100">
        <h2 className="text-base font-medium text-ink-900">{title}</h2>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      </header>
      <div>{children}</div>
    </section>
  );
}

function SideSection({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="mb-2.5">
        {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
        <h3 className="text-sm font-medium text-ink-900">{title}</h3>
      </header>
      <div>{children}</div>
    </section>
  );
}

function DescList({
  items,
  dense = false,
}: {
  items: { label: string; value: React.ReactNode }[];
  dense?: boolean;
}) {
  const rowPad = dense ? "py-1.5" : "py-2";
  return (
    <dl className="text-sm">
      {items.map(({ label, value }, i) => (
        <div
          key={label}
          className={`grid grid-cols-[90px_1fr] items-center gap-3 ${rowPad} ${
            i > 0 ? "border-t border-ink-100" : ""
          }`}
        >
          <dt className="text-xs text-ink-500">{label}</dt>
          <dd className="text-ink-800 min-w-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ── Status breakdown ───────────────────────────────────────────────────── */

function StatusBreakdown({
  meetings,
  className,
}: {
  meetings: MeetingCounts;
  className?: string;
}) {
  // Four chips: created / rescheduled / cancelled / rejected. Quiet when
  // n=0 so the eye finds the nonzero values.
  const chips: { label: string; n: number; Icon: typeof CalendarCheck; tone: string }[] = [
    { label: "Created",     n: meetings.created,     Icon: CalendarCheck, tone: "emerald" },
    { label: "Rescheduled", n: meetings.rescheduled, Icon: RefreshCw,     tone: "amber" },
    { label: "Cancelled",   n: meetings.cancelled,   Icon: CalendarX,     tone: "rose" },
    { label: "Rejected",    n: meetings.rejected,    Icon: XCircle,       tone: "ink" },
  ];
  return (
    <div className={`grid grid-cols-2 sm:grid-cols-4 gap-2 ${className ?? ""}`}>
      {chips.map(({ label, n, Icon, tone }) => (
        <div
          key={label}
          className={`rounded-md border px-3 py-2 ${
            n === 0
              ? "border-ink-100 text-ink-400"
              : tone === "emerald" ? "border-emerald-200/70 text-emerald-800"
              : tone === "amber"   ? "border-amber-200/70 text-amber-800"
              : tone === "rose"    ? "border-rose-200/70 text-rose-800"
              : "border-ink-200 text-ink-800"
          }`}
        >
          <div className="flex items-center gap-1.5 text-[0.65rem] uppercase tracking-[0.06em] opacity-80">
            <Icon className="h-3 w-3" />
            {label}
          </div>
          <div className="text-lg font-semibold mt-0.5 tabular-nums">{n}</div>
        </div>
      ))}
    </div>
  );
}

/* ── Bookings list ──────────────────────────────────────────────────────── */

function BookingsList({ bookings }: { bookings: BookingRow[] }) {
  if (bookings.length === 0) {
    return (
      <div className="text-sm text-ink-500 italic">
        No bookings yet. They&apos;ll appear here as soon as the platform webhook delivers one.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto -mx-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-ink-500 text-[0.65rem] uppercase tracking-[0.06em]">
            <th className="text-left font-medium px-2 py-2">Prospect</th>
            <th className="text-left font-medium px-2 py-2">When</th>
            <th className="text-left font-medium px-2 py-2">Status</th>
            <th className="text-left font-medium px-2 py-2">Reminders</th>
            <th className="text-left font-medium px-2 py-2">Video</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {bookings.map((b) => (
            <tr key={b.cal_booking_uid} className="align-top">
              <td className="px-2 py-3">
                <div className="font-medium text-ink-900">{b.prospect_name || "—"}</div>
                <div className="text-xs text-ink-500">
                  {b.prospect_email || ""}
                  {b.prospect_company ? ` · ${b.prospect_company}` : ""}
                </div>
              </td>
              <td className="px-2 py-3 text-ink-700 whitespace-nowrap">
                {b.scheduled_at ? <FormatDate iso={b.scheduled_at} tz={b.timezone} /> : <span className="text-ink-400">—</span>}
              </td>
              <td className="px-2 py-3">
                <StatusPill event={b.current_event} />
              </td>
              <td className="px-2 py-3">
                <ReminderBadge counts={b.reminders} />
              </td>
              <td className="px-2 py-3">
                {b.video_link ? (
                  <a
                    href={b.video_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-700 hover:text-brand-800 text-xs"
                  >
                    <Video className="h-3.5 w-3.5" />
                    join
                  </a>
                ) : (
                  <span className="text-ink-400 text-xs">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReminderBadge({ counts }: { counts: BookingRow["reminders"] }) {
  if (!counts) return <span className="text-xs text-ink-400">—</span>;
  const total = counts.pending + counts.processing + counts.sent + counts.failed + counts.cancelled;
  if (total === 0) return <span className="text-xs text-ink-400">—</span>;
  const tooltip =
    `pending ${counts.pending} · processing ${counts.processing} · ` +
    `sent ${counts.sent} · failed ${counts.failed} · cancelled ${counts.cancelled}`;
  return (
    <div className="flex items-center gap-1.5 text-xs" title={tooltip}>
      <Bell className="h-3 w-3 text-brand-600" />
      <span className="text-ink-700">
        {counts.pending + counts.processing > 0 && (
          <span className="font-medium">{counts.pending + counts.processing} pending</span>
        )}
        {counts.pending + counts.processing > 0 && counts.sent > 0 && " · "}
        {counts.sent > 0 && (
          <span className="text-emerald-700">{counts.sent} sent</span>
        )}
        {counts.failed > 0 && (
          <>
            {" · "}
            <span className="text-rose-700">{counts.failed} failed</span>
          </>
        )}
      </span>
    </div>
  );
}

function StatusPill({ event }: { event: BookingRow["current_event"] }) {
  const map = {
    BOOKING_CREATED:     { label: "Booked",      cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    BOOKING_RESCHEDULED: { label: "Rescheduled", cls: "bg-amber-50 text-amber-700 border-amber-200" },
    BOOKING_CANCELLED:   { label: "Cancelled",   cls: "bg-rose-50 text-rose-700 border-rose-200" },
    BOOKING_REJECTED:    { label: "Rejected",    cls: "bg-ink-100 text-ink-700 border-ink-200" },
  } as const;
  const m = map[event] ?? { label: event, cls: "bg-ink-100 text-ink-700 border-ink-200" };
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${m.cls}`}>
      {m.label}
    </span>
  );
}

function FormatDate({ iso, tz }: { iso: string; tz: string | null }) {
  const d = new Date(iso);
  const opts: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: tz || "UTC",
    timeZoneName: "short",
  };
  return <span>{new Intl.DateTimeFormat("en-US", opts).format(d)}</span>;
}
