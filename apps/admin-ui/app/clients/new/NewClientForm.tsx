"use client";

import Link from "next/link";
import { useActionState, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Loader2,
  Plus,
} from "lucide-react";
import { checkSlugAction, provisionSingleAction, type SingleResult } from "@/app/actions/provision";
import type { SlugCheck } from "@/lib/api";
import { Avatar } from "@/components/Avatar";
import { Reveal } from "@/components/Reveal";
import { CopyButton } from "@/components/CopyButton";
import { TimezoneCombobox } from "@/components/TimezoneCombobox";

// Mirrors the admin-api regex (slug.py) so we don't waste a round-trip on
// inputs we know cal.diy will reject.
const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/;

// Fallback list used when Intl.supportedValuesOf isn't available (very old
// browsers). The browser-derived list always wins when present — this just
// keeps the form usable on Safari <15.4 / Chrome <99 / Firefox <93.
const TIMEZONE_FALLBACK = [
  "UTC",
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Toronto", "America/Vancouver", "America/Mexico_City", "America/Sao_Paulo",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Amsterdam",
  "Europe/Rome", "Europe/Stockholm", "Europe/Zurich", "Europe/Istanbul",
  "Africa/Cairo", "Africa/Lagos", "Africa/Johannesburg",
  "Asia/Dubai", "Asia/Karachi", "Asia/Kolkata", "Asia/Bangkok",
  "Asia/Singapore", "Asia/Hong_Kong", "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai",
  "Australia/Perth", "Australia/Sydney", "Australia/Melbourne",
  "Pacific/Auckland",
];

type LiveStatus =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "ok"; data: SlugCheck }
  | { kind: "error"; message: string };

export function NewClientForm({ existingSlugs = [] }: { existingSlugs?: string[] }) {
  const [state, action, pending] = useActionState<SingleResult | undefined, FormData>(provisionSingleAction, undefined);
  const [slugInput, setSlugInput] = useState("");
  const [live, setLive] = useState<LiveStatus>({ kind: "idle" });

  // cal.diy treats slugs as case-insensitive usernames, so compare lowercased.
  const existingSlugSet = useMemo(
    () => new Set(existingSlugs.map((s) => s.trim().toLowerCase())),
    [existingSlugs],
  );

  // Browser-derived IANA timezone list — same data cal.com uses. Falls
  // back to a 30ish curated list on browsers that lack
  // Intl.supportedValuesOf (Safari <15.4 / Chrome <99 / Firefox <93).
  // Computed once per mount; the list is constant for the page session.
  const timezones = useMemo<string[]>(() => {
    try {
      const sv = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf;
      if (typeof sv === "function") {
        const list = sv("timeZone");
        if (Array.isArray(list) && list.length > 0) {
          // Sort so the dropdown reads predictably; native datalist
          // doesn't filter the *order*, just visibility, so a sorted
          // list also reads better when scrolled.
          return [...list].sort((a, b) => a.localeCompare(b));
        }
      }
    } catch {
      /* fall through */
    }
    return TIMEZONE_FALLBACK;
  }, []);
  const normalizedSlug = slugInput.trim().toLowerCase();
  const localTaken = normalizedSlug.length > 0 && existingSlugSet.has(normalizedSlug);
  const formatBad = normalizedSlug.length > 0 && !SLUG_RE.test(normalizedSlug);
  // Live (cal.diy) result is authoritative when we have it. Until then the
  // local-manifest check provides a fast path for the common case.
  const liveTaken = live.kind === "ok" && live.data.taken_in_cal === true;
  const slugTaken = localTaken || liveTaken;

  // Debounced live check. Fires 350ms after the user stops typing, only
  // when the format is sane and the local check hasn't already failed
  // (no point round-tripping when we already know it's taken).
  const inflight = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!normalizedSlug || formatBad || localTaken) {
      setLive({ kind: "idle" });
      return;
    }
    setLive({ kind: "checking" });
    const handle = setTimeout(async () => {
      // Cancel any earlier in-flight call so out-of-order responses can't
      // overwrite the latest answer.
      inflight.current?.abort();
      const ac = new AbortController();
      inflight.current = ac;
      try {
        const res = await checkSlugAction(normalizedSlug);
        if (ac.signal.aborted) return;
        if (res.ok) {
          setLive({ kind: "ok", data: res.data });
        } else {
          setLive({ kind: "error", message: res.error });
        }
      } catch (err) {
        if (!ac.signal.aborted) {
          setLive({ kind: "error", message: String(err) });
        }
      }
    }, 350);
    return () => {
      clearTimeout(handle);
      inflight.current?.abort();
    };
  }, [normalizedSlug, formatBad, localTaken]);

  if (state?.ok) {
    const r = state.data.record;
    return (
      <div className="animate-fade-in space-y-8">
        {/* Result strip: subdued, no card box, just an inline status line.
            The two key handoffs (booking link + first-login password) get
            their own flat blocks below. */}
        <div className="flex items-start gap-3">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-base font-medium text-ink-900">
              {state.data.created ? "Client provisioned" : "Client updated"}
            </h2>
            <p className="text-sm text-ink-500 mt-0.5">
              {r.email} is ready. Share the booking link and the first-login password through a secure channel.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Avatar seed={r.full_name || r.email} size="lg" />
          <div className="min-w-0">
            <div className="font-medium text-ink-900 truncate">{r.full_name}</div>
            <div className="text-xs text-ink-500 truncate">{r.email}</div>
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <div className="label">Booking link</div>
            <div className="flex items-center gap-2 rounded-lg border border-ink-200 bg-ink-50/40 px-3 py-2">
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
            <div className="label">First-login password</div>
            <Reveal value={r.password} />
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
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
    <form action={action} className="divide-y divide-ink-100">
      <Section
        title="Identity"
        description="The client's name + email become the bookings@glnkco.com login. The slug becomes their booking-link path."
      >
        <Field id="full_name" label="Full name" placeholder="Acme Inc" required />
        <Field id="email" label="Email" type="email" placeholder="founder@acme.com" required />
        <div>
          <label htmlFor="slug" className="label">Slug</label>
          <div className="relative">
            <input
              id="slug"
              name="slug"
              type="text"
              required
              placeholder="acme"
              value={slugInput}
              onChange={(e) => setSlugInput(e.target.value)}
              aria-invalid={(slugTaken || formatBad) || undefined}
              aria-describedby="slug-feedback"
              className={`input ${slugTaken || formatBad ? "border-rose-300 focus:border-rose-500" : ""}`}
            />
            {/* Right-side status indicator: spinner while checking, check
                when verified free. Sits inside the input visually. */}
            {normalizedSlug && !slugTaken && !formatBad && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                {live.kind === "checking" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-ink-400" />
                ) : live.kind === "ok" && live.data.available ? (
                  <CheckCircle className="h-4 w-4 text-emerald-600" />
                ) : null}
              </span>
            )}
          </div>
          <SlugFeedback
            normalizedSlug={normalizedSlug}
            formatBad={formatBad}
            localTaken={localTaken}
            live={live}
          />
        </div>
      </Section>

      <Section
        title="Schedule"
        description="Working hours apply to the client's timezone. Defaults are Mon–Fri 09:00–18:00."
      >
        <div>
          <label htmlFor="timezone" className="label">Timezone</label>
          <TimezoneCombobox
            id="timezone"
            name="timezone"
            options={timezones}
            defaultValue="America/New_York"
            placeholder="Click or type — e.g. Europe/Berlin"
            required
          />
          <p className="hint">
            {timezones.length} zones — click to browse, type to filter.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field id="work_start" label="Work start" defaultValue="09:00" hint="HH:MM in client's tz." />
          <Field id="work_end" label="Work end" defaultValue="18:00" />
        </div>
      </Section>

      <Section
        title="Fallback"
        description="Used by the outage page when bookings@glnkco.com is unreachable. Optional."
      >
        <Field
          id="calendly_url"
          label="Calendly URL"
          placeholder="https://calendly.com/.../30min"
        />
      </Section>

      <div className="pt-6 flex items-center justify-end gap-2">
        {state && !state.ok && (
          <p role="alert" className="text-sm text-rose-700 flex-1 flex items-start gap-1.5">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{state.error}</span>
          </p>
        )}
        <Link href="/" className="btn-secondary">Cancel</Link>
        <button type="submit" disabled={pending || slugTaken} className="btn-primary">
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

function SlugFeedback({
  normalizedSlug,
  formatBad,
  localTaken,
  live,
}: {
  normalizedSlug: string;
  formatBad: boolean;
  localTaken: boolean;
  live: LiveStatus;
}) {
  // Precedence: format error → local manifest collision → live cal.diy
  // collision → live unknown (e.g. CAL_DB_URL unset) → all clear / hint.
  // Always render under id="slug-feedback" so aria-describedby targets it.
  if (formatBad) {
    return (
      <p id="slug-feedback" className="mt-1.5 text-xs text-rose-700 flex items-start gap-1.5">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>
          Use lowercase letters, digits, and hyphens (2–40 chars). It becomes the URL path.
        </span>
      </p>
    );
  }
  if (localTaken) {
    return (
      <p id="slug-feedback" className="mt-1.5 text-xs text-rose-700 flex items-start gap-1.5">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>
          &ldquo;{normalizedSlug}&rdquo; is already provisioned by us. Pick another.
        </span>
      </p>
    );
  }
  if (live.kind === "ok" && live.data.taken_in_cal === true) {
    return (
      <p id="slug-feedback" className="mt-1.5 text-xs text-rose-700 flex items-start gap-1.5">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>
          &ldquo;{normalizedSlug}&rdquo; is already taken on cal.diy by another account (not via this admin).
        </span>
      </p>
    );
  }
  if (live.kind === "ok" && live.data.taken_in_cal === null && normalizedSlug) {
    // Live check unavailable — the local manifest is our only signal.
    return (
      <p id="slug-feedback" className="mt-1.5 text-xs text-amber-700 flex items-start gap-1.5">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>
          Couldn&apos;t check cal.diy directly — proceeding will still error if the slug is taken there.
        </span>
      </p>
    );
  }
  if (live.kind === "ok" && live.data.available) {
    return (
      <p id="slug-feedback" className="mt-1.5 text-xs text-emerald-700 flex items-start gap-1.5">
        <CheckCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>Available. Becomes the bookings@glnkco.com username.</span>
      </p>
    );
  }
  return (
    <p id="slug-feedback" className="hint">
      Becomes the bookings@glnkco.com username and the booking-link path.
    </p>
  );
}

/* Section — flat, no card. Title + description sit above a stack of
 * fields. Sibling sections are visually separated by a hairline rule
 * via the parent <form>'s `divide-y divide-ink-100`. */
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-5 py-6 first:pt-0 md:grid-cols-[200px_1fr]">
      <div className="md:pt-1">
        <h3 className="text-sm font-medium text-ink-900">{title}</h3>
        <p className="text-xs text-ink-500 mt-1 leading-relaxed">{description}</p>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

/* Field — minimal input wrapper. No leading icons; the label carries the
 * meaning. `hint` is an optional sub-label rendered below. */
function Field({
  id,
  label,
  hint,
  ...props
}: {
  id: string;
  label: string;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input id={id} name={id} {...props} className="input" />
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}
