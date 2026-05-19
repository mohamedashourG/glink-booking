"use client";

import { useState, useTransition } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Loader2,
  Plus,
  Save,
  X,
} from "lucide-react";
import {
  setReminderConfigAction,
  type SetReminderConfigResult,
} from "@/app/actions/reminders";
import type { ReminderConfig, ReminderRole } from "@/lib/api";

/** Save-handler shape. Server Actions (admin context) and direct fetch
 *  (portal iframe context) both adhere to this. Centralising it here
 *  means the editor body is agnostic to *how* the save happens. */
type SaveFn = (body: {
  offsets_min: number[];
  recipients: ReminderRole[];
}) => Promise<SetReminderConfigResult>;

const ALL_ROLES: { value: ReminderRole; label: string; hint: string }[] = [
  { value: "prospect", label: "Prospect",  hint: "The person who booked the meeting." },
  { value: "host",     label: "Host",       hint: "Your cal.diy client (the meeting owner)." },
  { value: "agency",   label: "Agency",     hint: "AGENCY_NOTIFY_EMAIL — the agency inbox." },
];

const PRESETS: { label: string; minutes: number }[] = [
  { label: "15 min",  minutes: 15 },
  { label: "30 min",  minutes: 30 },
  { label: "1 hour",  minutes: 60 },
  { label: "2 hours", minutes: 120 },
  { label: "4 hours", minutes: 240 },
  { label: "1 day",   minutes: 1440 },
  { label: "2 days",  minutes: 2880 },
];

function labelFor(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 1440) {
    const h = minutes / 60;
    return `${Number.isInteger(h) ? h : h.toFixed(1)} hour${h === 1 ? "" : "s"}`;
  }
  const d = minutes / 1440;
  return `${Number.isInteger(d) ? d : d.toFixed(1)} day${d === 1 ? "" : "s"}`;
}

export function ReminderEditor({
  slug,
  initial,
  saveOverride,
}: {
  slug: string;
  initial: ReminderConfig;
  /** Optional. When supplied, the editor uses this instead of the
   *  default Server Action (admin path). The portal iframe page passes
   *  its own fetch-based handler that uses an in-memory portal session
   *  token. */
  saveOverride?: SaveFn;
}) {
  // Local state is the source of truth while the form is open; we
  // overwrite it from server response after Save lands. `initial.is_default`
  // means there's no per-client row yet — saving creates one for the first
  // time. We still show the values though, so the operator can adjust
  // *from* the default rather than starting blank.
  const [offsets, setOffsets] = useState<number[]>(() =>
    // Show sorted descending so longer notice appears first — matches
    // how admin-api normalizes on save.
    [...initial.offsets_min].sort((a, b) => b - a),
  );
  const [recipients, setRecipients] = useState<ReminderRole[]>(
    () => [...initial.recipients],
  );
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<SetReminderConfigResult | null>(null);
  const [savedConfig, setSavedConfig] = useState<ReminderConfig>(initial);
  const [customInput, setCustomInput] = useState("");

  // Dirty detection: compare current local state to the last-saved server
  // state. We compare *content* (sorted offsets, sorted recipients), not
  // referential equality — so reordering the same values doesn't count.
  const dirty =
    JSON.stringify([...offsets].sort((a, b) => a - b)) !==
      JSON.stringify([...savedConfig.offsets_min].sort((a, b) => a - b)) ||
    JSON.stringify([...recipients].sort()) !==
      JSON.stringify([...savedConfig.recipients].sort());

  function toggleRole(role: ReminderRole) {
    setRecipients((cur) =>
      cur.includes(role) ? cur.filter((r) => r !== role) : [...cur, role],
    );
  }

  function addOffset(n: number) {
    if (!Number.isFinite(n) || n < 1 || n > 43200) return;
    if (offsets.includes(n)) return;
    setOffsets((cur) => [...cur, n].sort((a, b) => b - a));
  }

  function removeOffset(n: number) {
    setOffsets((cur) => cur.filter((x) => x !== n));
  }

  function onAddCustom() {
    // Accept "60", "2h", "1d", "30 min" — friendly parse so the operator
    // doesn't have to think in minutes.
    const raw = customInput.trim().toLowerCase();
    if (!raw) return;
    const match = raw.match(/^(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)?$/);
    if (!match) {
      setCustomInput("");
      return;
    }
    const value = parseFloat(match[1]);
    const unit = match[2] || "m";
    let minutes = value;
    if (unit.startsWith("h")) minutes = value * 60;
    else if (unit.startsWith("d")) minutes = value * 1440;
    minutes = Math.round(minutes);
    addOffset(minutes);
    setCustomInput("");
  }

  function onSave() {
    setResult(null);
    startTransition(async () => {
      const body = { offsets_min: offsets, recipients };
      const res = saveOverride
        ? await saveOverride(body)
        : await setReminderConfigAction(slug, body);
      setResult(res);
      if (res.ok) {
        // Update the comparison baseline so dirty goes back to false until
        // the operator edits again.
        setSavedConfig(res.config);
        setOffsets([...res.config.offsets_min]);
        setRecipients([...res.config.recipients]);
      }
    });
  }

  const empty = offsets.length === 0 || recipients.length === 0;

  // Outer card removed — the parent <Section> on the detail page handles
  // titling and the hairline rule. This component now just owns the form
  // body so it fits cleanly into the flat layout.
  return (
    <div>
      {/* Offsets ---------------------------------------------------------- */}
      <div className="mb-5">
        <div className="label mb-1">When to send</div>
        <p className="hint mb-2">
          One email per offset, per selected recipient. Lower the value to remind closer to the meeting.
        </p>
        <div className="flex flex-wrap gap-2 mb-2">
          {offsets.length === 0 && (
            <span className="text-xs text-rose-600 italic flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              No offsets — reminders are off for this client
            </span>
          )}
          {offsets.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => removeOffset(m)}
              className="inline-flex items-center gap-1 rounded-full bg-brand-50 border border-brand-200 px-2.5 py-1 text-xs text-brand-800 hover:bg-rose-50 hover:border-rose-300 hover:text-rose-700"
              title="Remove this offset"
            >
              {labelFor(m)} before
              <X className="h-3 w-3" />
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="flex gap-1">
            {PRESETS.filter((p) => !offsets.includes(p.minutes)).map((p) => (
              <button
                key={p.minutes}
                type="button"
                onClick={() => addOffset(p.minutes)}
                className="inline-flex items-center gap-1 rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-600 hover:bg-ink-50"
              >
                <Plus className="h-3 w-3" />
                {p.label}
              </button>
            ))}
          </div>
          <div className="flex gap-1 ml-1">
            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  onAddCustom();
                }
              }}
              placeholder="custom (e.g. 45m, 3h)"
              className="input text-xs py-1 px-2 w-32"
            />
            <button
              type="button"
              onClick={onAddCustom}
              className="btn-secondary btn-sm"
            >
              Add
            </button>
          </div>
        </div>
      </div>

      {/* Recipients ------------------------------------------------------- */}
      <div className="mb-5">
        <div className="label mb-1">Who gets the reminder</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {ALL_ROLES.map((r) => (
            <label
              key={r.value}
              className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors ${
                recipients.includes(r.value)
                  ? "border-brand-300 bg-brand-50/60"
                  : "border-ink-200 hover:bg-ink-50/60"
              }`}
            >
              <input
                type="checkbox"
                checked={recipients.includes(r.value)}
                onChange={() => toggleRole(r.value)}
                className="mt-0.5"
              />
              <div className="min-w-0">
                <div className="text-sm font-medium text-ink-900">{r.label}</div>
                <div className="text-[0.7rem] text-ink-500">{r.hint}</div>
              </div>
            </label>
          ))}
        </div>
        {recipients.length === 0 && (
          <p className="mt-1.5 text-xs text-rose-600 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            No recipients selected — saving will disable reminders for this client.
          </p>
        )}
      </div>

      {/* Footer: result + save ------------------------------------------- */}
      <div className="flex items-center justify-between gap-3 border-t border-ink-100 pt-4">
        <div className="min-w-0">
          {result && !result.ok && (
            <p className="text-xs text-rose-700 flex items-start gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>{result.error}</span>
            </p>
          )}
          {result && result.ok && !dirty && (
            <p className="text-xs text-emerald-700 flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5" />
              Saved. Applies to new bookings going forward.
            </p>
          )}
          {!result && empty && (
            <p className="text-xs text-ink-500">
              Save with empty values to disable reminders for this client.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onSave}
          disabled={pending || !dirty}
          className="btn-primary"
          title={!dirty ? "No changes" : "Save reminder policy for this client"}
        >
          {pending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              Save
            </>
          )}
        </button>
      </div>
    </div>
  );
}
