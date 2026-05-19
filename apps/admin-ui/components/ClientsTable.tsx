"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowUpRight, Calendar, Inbox, RefreshCw, UserPlus } from "lucide-react";
import { Avatar } from "./Avatar";
import { CopyButton } from "./CopyButton";
import { CoverageBadge } from "./CoverageBadge";
import { SearchInput } from "./SearchInput";
import type { ListedClient } from "@/lib/api";

export function ClientsTable({
  clients,
  publicBase,
}: {
  clients: ListedClient[];
  publicBase: string;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return clients;
    return clients.filter(
      (c) =>
        c.slug.toLowerCase().includes(needle) ||
        c.full_name.toLowerCase().includes(needle) ||
        c.email.toLowerCase().includes(needle),
    );
  }, [q, clients]);

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border-b border-ink-100">
        <SearchInput value={q} onChange={setQ} placeholder="Search by name, email, or slug…" />
        <div className="text-xs text-ink-500">
          {filtered.length === clients.length
            ? `${clients.length} client${clients.length === 1 ? "" : "s"}`
            : `${filtered.length} of ${clients.length}`}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState hasClients={clients.length > 0} clearQuery={() => setQ("")} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-500 text-[0.7rem] uppercase tracking-[0.06em]">
                <th className="text-left font-semibold px-4 py-3">Client</th>
                <th className="text-left font-semibold px-4 py-3">Booking link</th>
                <th className="text-left font-semibold px-4 py-3">Meetings</th>
                <th className="text-left font-semibold px-4 py-3">Coverage</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {filtered.map((c) => {
                // effective_slug is whatever cal.diy currently has (falls
                // back to stored slug when the live lookup is unavailable).
                // We render booking links from it so they don't 404 after a
                // user renames themselves in cal.diy.
                const linkSlug = c.effective_slug || c.slug;
                const bookingLink = `${publicBase}/${linkSlug}/30min`;
                const m = c.meetings;
                return (
                  <tr key={c.email} className="group hover:bg-ink-50/60 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <Avatar seed={c.full_name || c.email} size="md" />
                        <div className="min-w-0">
                          <div className="font-medium text-ink-900 truncate">{c.full_name || linkSlug}</div>
                          <div className="text-xs text-ink-500 truncate">{c.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <a
                          href={bookingLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-brand-700 hover:text-brand-800 font-medium"
                        >
                          {linkSlug}/30min
                          <ArrowUpRight className="h-3.5 w-3.5 opacity-60" />
                        </a>
                        <CopyButton value={bookingLink} variant="ghost" />
                      </div>
                      {c.drift && (
                        <div
                          className="mt-1 inline-flex items-center gap-1 rounded-md bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[0.65rem] text-amber-800"
                          title={`Stored slug "${c.slug}" differs from cal.diy username "${c.live_username}". cal.diy is authoritative.`}
                        >
                          <RefreshCw className="h-3 w-3" />
                          renamed in cal.diy (was {c.slug})
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <MeetingCount meetings={m} />
                    </td>
                    <td className="px-4 py-3">
                      <CoverageBadge value={c.webhook_coverage} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/clients/${encodeURIComponent(c.slug)}`}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-ink-600 group-hover:text-ink-900 hover:bg-ink-100"
                      >
                        Details
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MeetingCount({ meetings }: { meetings: import("@/lib/api").MeetingCounts }) {
  if (meetings.total === 0) {
    return <span className="text-xs text-ink-400">—</span>;
  }
  // Active = booked and not cancelled/rejected. Useful at-a-glance signal
  // separate from raw total (which includes cancellations).
  const active = meetings.created + meetings.rescheduled;
  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center gap-1 rounded-md bg-brand-50 text-brand-700 px-2 py-0.5 text-xs font-medium">
        <Calendar className="h-3 w-3" />
        {meetings.total}
      </span>
      {meetings.cancelled + meetings.rejected > 0 && (
        <span
          className="text-[0.65rem] text-ink-500"
          title={`${active} active · ${meetings.cancelled} cancelled · ${meetings.rejected} rejected`}
        >
          {active} active
        </span>
      )}
    </div>
  );
}

function EmptyState({ hasClients, clearQuery }: { hasClients: boolean; clearQuery: () => void }) {
  if (hasClients) {
    return (
      <div className="px-4 py-16 text-center">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-100 text-ink-500">
          <Inbox className="h-6 w-6" />
        </div>
        <h3 className="mt-3 text-sm font-medium text-ink-900">No matches</h3>
        <p className="mt-1 text-xs text-ink-500">Try a different search term.</p>
        <button onClick={clearQuery} className="btn-secondary mt-4 btn-sm">Clear search</button>
      </div>
    );
  }
  return (
    <div className="px-4 py-16 text-center">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-600">
        <UserPlus className="h-6 w-6" />
      </div>
      <h3 className="mt-3 text-sm font-medium text-ink-900">No clients yet</h3>
      <p className="mt-1 text-xs text-ink-500">Provision your first client to get started.</p>
      <Link href="/clients/new" className="btn-primary mt-4 btn-sm">Add client</Link>
    </div>
  );
}
