# UI map

Every user-facing surface in the booking system: who interacts with it,
what they do, where it lives. Reference doc — walked from the codebase
on the date of the last commit, not from memory. Cite paths back to the
source if you need to verify or fix something.

Two codebases are in scope:

- **bookings@glnkco.com** — vendored at `cal.diy/`; everything in `apps/web/app/*`
  is App Router (Next.js 15), `apps/web/pages/*` is the legacy Pages
  Router and only carries framework wiring + the routing-form embed.
  All path citations below are relative to `cal.diy/`.
- **fallback** — at `glink-booking/apps/fallback/`; static export.

The bookings@glnkco.com app router uses route groups in parentheses (e.g.
`(use-page-wrapper)`, `(settings-layout)`) — those parens **do not**
appear in the URL. So `apps/web/app/(use-page-wrapper)/settings/(settings-layout)/my-account/calendars/page.tsx`
serves at `/settings/my-account/calendars`.

---

## bookings@glnkco.com — PROSPECT-facing

The public booking flow. No login, anyone with the link.

| Path | What the prospect does | Source | Dependencies |
|---|---|---|---|
| `/<slug>` | Lands on the host's public booking page. Sees host name + bio + their visible event types. Picks one. | `apps/web/app/(booking-page-wrapper)/[user]/page.tsx` | none — works as soon as the host is provisioned |
| `/<slug>/<event-type-slug>` | Booker grid: month → day → 30-min slots. Picks a slot, fills name/email + custom questions (`Company`, `What would you like to discuss?`), submits. | `apps/web/app/(booking-page-wrapper)/[user]/[type]/page.tsx` | available-slot computation needs a working schedule + (eventually) calendar busy-times |
| `/booking/<uid>` | Confirmation screen after a successful booking — meeting summary, add-to-calendar, reschedule/cancel links | `apps/web/app/(booking-page-wrapper)/booking/[uid]/page.tsx` | none |
| `/booking-successful/<uid>` | Alternate success surface used by some booking flows | `apps/web/app/(booking-page-wrapper)/booking-successful/[uid]/page.tsx` | none |
| `/reschedule/<uid>` | "Pick a new time" surface for an existing booking — same booker grid, scoped to the same event type, bookings@glnkco.com mints a NEW uid for the rescheduled booking | `apps/web/app/reschedule/[uid]/page.tsx` | none |
| `/booking/<uid>` (cancel action) | The cancel flow lives on the same confirmation surface — clicking "Cancel" pops a reason form and POSTs `/api/cancel`. There is no standalone `/cancel/<uid>` page. | same as above | none |
| `/d/<link>/<slug>` | Hashed/private one-off booking link — same booker UI but only resolvable via the secret URL | `apps/web/app/(booking-page-wrapper)/d/[link]/[slug]/page.tsx` | needs the host to have generated the hashed link |
| `/payment/<uid>` | Paid-event payment screen. **Not used in our setup** — every event type is free. | `apps/web/app/(use-page-wrapper)/payment/[uid]/page.tsx` | Stripe Connect on the host's account |
| `/video/<uid>` + `/video/meeting-ended/<uid>` + `/video/meeting-not-started/<uid>` + `/video/no-meeting-found` | The Cal Video meeting room and its in-flight error states (e.g. arriving early, already finished). Used when the meeting location is `integrations:daily` (Cal Video). | `apps/web/app/(use-page-wrapper)/video/*/page.tsx` | Daily.co API key configured in bookings@glnkco.com env |

---

## bookings@glnkco.com — CLIENT-facing

The provisioned host's surfaces. Auth + the bits of `/settings` they
actually need to touch.

### Auth

| Path | Action | Source | Dependencies |
|---|---|---|---|
| `/auth/login` | Email + password sign-in (`identityProvider=CAL` users — i.e. ours). Also offers OAuth buttons if any provider is configured. | `apps/web/app/(use-page-wrapper)/auth/login/page.tsx` | none for credentials login; Google OAuth login needs `GOOGLE_LOGIN_ENABLED=true` + `GOOGLE_API_CREDENTIALS` |
| `/auth/signin` | Alias / NextAuth-style entry — same form. | `apps/web/app/(use-page-wrapper)/auth/signin/page.tsx` | same as above |
| `/signup` | Self-serve signup (we do not normally use this — clients arrive pre-provisioned by the CLI). Disabled when `NEXT_PUBLIC_DISABLE_SIGNUP=true`. | `apps/web/app/(use-page-wrapper)/signup/page.tsx` (POST handler at `apps/web/app/api/auth/signup/route.ts`) | mailhog/SMTP only if email-verification is enforced |
| `/auth/forgot-password` + `/auth/forgot-password/<id>` | Request a password-reset link, then complete the reset using the link. Critical — clients use this if they lose the temporary password from the welcome email. | `apps/web/app/(use-page-wrapper)/auth/forgot-password/{page,[id]}/*` | working SMTP (Resend / mailhog) so the reset email actually sends |
| `/auth/verify-email` + `/auth/verify-email-change` | Email-verification landing pages. Reachable when the `email-verification` feature flag is on (it is, by default in this build). | `apps/web/app/(use-page-wrapper)/auth/verify-email/*` | working SMTP |
| `/auth/setup` | First-time instance setup wizard — creates the system-admin user. Run **once** per bookings@glnkco.com install. After an admin exists, it redirects to `/auth/login`. | `apps/web/app/(use-page-wrapper)/auth/setup/page.tsx` (handler `apps/web/app/api/auth/setup/route.ts`) | none |
| `/auth/error` | Generic auth-error landing (e.g. NextAuth error param). Clients land here on bad login, etc. | `apps/web/app/(use-page-wrapper)/auth/error/page.tsx` | none |
| `/auth/logout` | Logout endpoint — clears NextAuth session and redirects. | `apps/web/app/(use-page-wrapper)/auth/logout/page.tsx` | none |

### Onboarding (first login after signup / via the welcome link)

| Path | Action | Source | Dependencies |
|---|---|---|---|
| `/getting-started/<step>` | Original onboarding flow — pick a username, connect calendar, set availability. | `apps/web/app/(use-page-wrapper)/getting-started/[[...step]]/page.tsx` | calendar OAuth wired (Google Calendar / Office 365) for the connect-calendar step |
| `/onboarding/getting-started` | Newer onboarding entrypoint (gated by `onboarding-v3` feature flag). | `apps/web/app/(use-page-wrapper)/onboarding/getting-started/page.tsx` | same |
| `/onboarding/personal/profile` | Confirm profile name/avatar. | `apps/web/app/(use-page-wrapper)/onboarding/personal/profile/page.tsx` | none |
| `/onboarding/personal/calendar` | Calendar-connect step inside the v3 flow. | `apps/web/app/(use-page-wrapper)/onboarding/personal/calendar/page.tsx` | Google / Microsoft OAuth credentials |
| `/onboarding/personal/settings` | Final-step "you're set" surface. | `apps/web/app/(use-page-wrapper)/onboarding/personal/settings/page.tsx` | none |

The redirect chain after first login is decided by `checkOnboardingRedirect()`
in `packages/features/auth/lib/onboardingUtils.ts` — the user lands on
the right onboarding step or, if already onboarded, on `/event-types`.

### Day-to-day surfaces

| Path | Action | Source | Dependencies |
|---|---|---|---|
| `/event-types` | Default landing after login — list of the host's event types, toggle visibility, edit. | `apps/web/app/(use-page-wrapper)/(main-nav)/event-types/page.tsx` | none |
| `/event-types/<id>` | Event-type editor: title, description, length, location, custom booking questions, buffers, notice, booking window, booking limits. **This is where everything our `defaults.py` writes is also editable by the host.** | `apps/web/app/(use-page-wrapper)/event-types/[type]/page.tsx` | none |
| `/availability` | List of schedules. Provisioning creates one called "Working Hours". | `apps/web/app/(use-page-wrapper)/(main-nav)/availability/page.tsx` | none |
| `/availability/<schedule>` | Schedule editor — drag day rows to widen/narrow working hours, set timezone, mark default. | `apps/web/app/(use-page-wrapper)/availability/[schedule]/page.tsx` | none |
| `/availability/troubleshoot` | Diagnostic view: shows the host what their computed busy/free looks like for a given day. | `apps/web/app/(use-page-wrapper)/availability/troubleshoot/page.tsx` | calendar OAuth wired (otherwise nothing to troubleshoot) |
| `/bookings/<status>` | Booking list filtered by `upcoming` / `recurring` / `past` / `cancelled` / `unconfirmed`. | `apps/web/app/(use-page-wrapper)/(main-nav)/bookings/[status]/page.tsx` | none |
| `/booking/<uid>/logs` | Per-booking audit trail (bookings@glnkco.com's internal log of state transitions on that booking — accessible by the host, not the prospect). | `apps/web/app/(use-page-wrapper)/(main-nav)/booking/[uid]/logs/page.tsx` | none |
| `/more` | Mobile/secondary-nav menu. | `apps/web/app/(use-page-wrapper)/more/page.tsx` | none |
| `/refer` | Referral-program surface — N/A for our setup (cal.com SaaS feature). | `apps/web/app/(use-page-wrapper)/refer/page.tsx` | — |
| `/upgrade` | Plan-upgrade page — N/A (bookings@glnkco.com is unlicensed; nothing to upgrade to). | `apps/web/app/(use-page-wrapper)/upgrade/page.tsx` | — |
| `/maintenance` | Static "we're down" page bookings@glnkco.com serves itself when the maintenance flag is on. **Not the same as our outage fallback** — this is shown by bookings@glnkco.com when bookings@glnkco.com is intentionally taken offline. | `apps/web/app/(use-page-wrapper)/maintenance/page.tsx` | maintenance-mode toggle |

### `/settings/my-account` — personal client settings

All under `apps/web/app/(use-page-wrapper)/settings/(settings-layout)/my-account/`:

| Path | Action | Source | Dependencies |
|---|---|---|---|
| `/settings/my-account/profile` | Name, username, bio, avatar, secondary emails. | `…/profile/page.tsx` | none |
| `/settings/my-account/general` | Language, timezone, time format, week start. **The timezone field here is the one prospects see availability in.** | `…/general/page.tsx` | none |
| `/settings/my-account/calendars` | Connect / disconnect Google Calendar, Office 365, Apple iCloud, etc. Pick which calendar bookings get written to. **The single most important client-facing setting** — without a connected calendar there's no busy-time data and prospects can book over real meetings. | `…/calendars/page.tsx` | calendar OAuth credentials wired in bookings@glnkco.com env (Google: `GOOGLE_API_CREDENTIALS`; Microsoft: `MS_GRAPH_CLIENT_ID/SECRET`); Apple needs only an app-specific password from the user |
| `/settings/my-account/conferencing` | Pick the default video provider (Cal Video / Google Meet / Zoom / etc.) for new event types. | `…/conferencing/page.tsx` | conferencing-app env (`ZOOM_CLIENT_ID/SECRET`, etc.) for non-Cal-Video options |
| `/settings/my-account/appearance` | Brand colors + dark/light theme for the host's booking page. | `…/appearance/page.tsx` | none |
| `/settings/my-account/out-of-office` | Block ranges where the host is unavailable. | `…/out-of-office/page.tsx` | none |
| `/settings/my-account/push-notifications` | Subscribe the browser to web-push notifications. | `…/push-notifications/page.tsx` | `NEXT_PUBLIC_VAPID_PUBLIC_KEY` + `VAPID_PRIVATE_KEY` |
| `/settings/security/password` | Change password. | `apps/web/app/(use-page-wrapper)/settings/(settings-layout)/security/password/page.tsx` | none |
| `/settings/security/two-factor-auth` | Enable / disable TOTP 2FA. | `…/two-factor-auth/page.tsx` | none |

### `/settings/developer` — only relevant if a client wants to integrate themselves

We do not ask clients to touch these — but they exist:

| Path | Action | Source | Notes |
|---|---|---|---|
| `/settings/developer/api-keys` | Create / list / revoke personal API keys. **Read works; the in-page "Create API key" button is dead in this build** — it calls `viewer.apiKeys.create` over tRPC and that route is not mounted. We don't need this UI for normal ops since our admin webhook is global. | `apps/web/app/(use-page-wrapper)/settings/(settings-layout)/developer/api-keys/page.tsx` | — |
| `/settings/developer/webhooks` | List of the user's webhooks. | `apps/web/app/(use-page-wrapper)/settings/(settings-layout)/developer/webhooks/(with-loader)/page.tsx` | — |
| `/settings/developer/webhooks/new` | Per-user webhook editor. | `…/webhooks/new/page.tsx` | — |
| `/settings/developer/webhooks/<id>` | Edit one. | `…/webhooks/[id]/page.tsx` | — |
| `/settings/developer/oauth` | OAuth-client management. Org-scoped — N/A in this build. | `…/developer/oauth/page.tsx` | — |

---

## bookings@glnkco.com — ADMIN-facing

System-admin surfaces. Only `users.role = 'ADMIN'` (the user created by
`/auth/setup`) can reach these — others get redirected.

| Path | Action | Source |
|---|---|---|
| `/settings/admin` | Admin home — links into the sub-pages below. | `apps/web/app/(use-page-wrapper)/settings/(admin-layout)/admin/page.tsx` |
| `/settings/admin/users` | List + search every user on the instance. | `…/admin/users/page.tsx` |
| `/settings/admin/users/<id>/edit` | Edit any user (role, lock/unlock, reset password). | `…/admin/users/[id]/edit/page.tsx` |
| `/settings/admin/users/add` | Create a user from the admin UI (we use the provisioning CLI instead). | `…/admin/users/add/page.tsx` |
| `/settings/admin/apps/<category>` | App-store admin — install/configure apps globally. | `…/admin/apps/[category]/page.tsx` |
| `/settings/admin/flags` | Feature-flag toggles. **The `email-verification` flag lives here** — turn it off if you don't want clients gated on verifying their email. | `…/admin/flags/page.tsx` |
| `/settings/admin/lockedSMS` | SMS-lock controls (out of scope for our setup). | `…/admin/lockedSMS/page.tsx` |
| `/settings/admin/oauth` | Instance-level OAuth-client provisioning (org-platform stuff; not used). | `…/admin/oauth/page.tsx` |
| `/settings/admin/playground` + `/settings/admin/playground/date-range-filter` | Internal cal.com dev sandbox — irrelevant. | `…/admin/playground/*` |
| `/auth/oauth2/authorize` | OAuth2 authorization screen — surfaces when a third party initiates an OAuth flow against the bookings@glnkco.com instance. | `apps/web/app/(use-page-wrapper)/auth/oauth2/authorize/page.tsx` |

**Webhook admin note:** there is **no UI for the platform-scoped global
webhook** in this build. The "Platform" group bookings@glnkco.com's source code
suggests it might surface (`packages/features/webhooks/lib/repository/WebhookRepository.ts:484`)
does not appear in the rendered settings page. We register and inspect
the platform webhook out-of-band — `glink-provision bootstrap-webhook`
to create, direct SQL against the `Webhook` table to inspect. See
RUNBOOK.md.

---

## fallback — outage backstop

Static Next.js 16 export at `glink-booking/apps/fallback/`. Routed to
when bookings@glnkco.com is unreachable (the routing layer that does the swap is
deploy-phase, not in this codebase). Zero runtime dependency on bookings@glnkco.com
or the receiver.

| Path | Who sees it | When | What it shows | Source |
|---|---|---|---|---|
| `/<slug>/` | Prospect | Their host's bookings@glnkco.com booking page is down | "Booking temporarily unavailable" + the host's name + a `mailto:` CTA. **If** the host has a `calendly_url` in the manifest, an inline Calendly embed below the email CTA. | `apps/fallback/app/[slug]/page.tsx` |
| `/` | Anyone hitting the fallback root without a slug | Same outage | Generic "booking page is offline, try again" placeholder. | `apps/fallback/app/page.tsx` |
| 404 (any unknown slug) | Anyone | When the requested slug isn't in `clients.json` | Clean "Not found" with a "Try the booking page" link back to bookings@glnkco.com. | `apps/fallback/app/not-found.tsx` |

The manifest the build reads is `glink-booking/.data/clients.json`,
written by every provisioning run. Dependencies: none for this app
itself; the per-host Calendly embed depends on the URL being valid (the
fallback doesn't validate it — Calendly renders its own 404 inside the
iframe if not).

---

## What there is no UI for

By design, per the brief's out-of-scope list. The agency operates
through code + 3rd-party tools, not a custom dashboard:

- **Provisioning a client** → `glink-provision single` / `glink-provision batch` CLI. No UI.
- **Bootstrap of the global webhook** → `glink-provision bootstrap-webhook`. No UI.
- **Viewing bookings by campaign / UTM source / client** → SQL against the receiver's Postgres (`bookings` table at `localhost:5433`, schema in `apps/receiver/src/receiver/schema.sql`). No UI.
- **Live booking notifications** → Slack `#bookings` channel (the receiver's Slack fan-out integration). No UI we built.
- **CRM view of any prospect** → HubSpot directly. No UI we built.
- **Email log of agency notifications** → Resend dashboard or your inbox. No UI we built.
- **Integration health (which fan-out targets are configured / healthy)** → receiver startup log line `fan-out integrations configured: [...]` and individual per-event log lines. No status page.
- **Platform webhook management** → SQL inspection of the `Webhook` table; CLI to bootstrap. No bookings@glnkco.com UI surfaces it.
- **Manifest of provisioned clients** → `cat .data/clients.json`. No UI.

---

## Branding state today

Everything on the bookings@glnkco.com side is vanilla cal.com out of the box. Phase
2 deploy work will replace these:

- **App name** — defaults to "Cal.diy". Source: `packages/lib/constants.ts:38` (`APP_NAME`). Override via `NEXT_PUBLIC_APP_NAME` env.
- **Email "From" name** — defaults to `APP_NAME`, so "Cal.diy". Source: `packages/lib/constants.ts:43` (`EMAIL_FROM_NAME`). Override via `EMAIL_FROM_NAME`.
- **Email "From" address** — `notifications@yourselfhostedcal.com` placeholder. Source: `cal.diy/.env.example:222`.
- **Logo / favicon** — cal.com's default. Served from `/api/logo` (bookings@glnkco.com supports custom logos through admin settings + asset upload).
- **Booking page colors** — cal.com brand colors (light: `#292929` accent; dark theme baked in). Per-host overridable in `/settings/my-account/appearance`, but the default cal.com palette is what new hosts get.
- **"Powered by Cal.com" footer** — appears on the public booking page when the cal.com hosted-features flag is on. With `NEXT_PUBLIC_HOSTED_CAL_FEATURES=` empty (our setting), the footer is suppressed in self-host mode. Worth re-checking before launch.
- **Email templates** — every confirmation / cancellation / reschedule email uses cal.com's default React Email template. Branding lives in `packages/emails/src/templates/*`.
- **Outage fallback** — neutral grey/white card, system font, no logo. The "real branding pass happens during the deploy phase" per the original brief; styles live in `apps/fallback/app/globals.css` and the agency-color pass replaces them.

---

## User journey appendix

### Journey 1 — A prospect books a meeting end-to-end

1. **Marketing surface (outside this repo)** — prospect clicks a link
   the host put in their email signature / LinkedIn / a campaign:
   `http://<cal-diy-host>/<slug>/30min?metadata[utm_source]=newsletter&metadata[utm_campaign]=q2_demo`.
2. **Booker grid** — `/<slug>/30min` (`apps/web/app/(booking-page-wrapper)/[user]/[type]/page.tsx`).
   Prospect sees host name + month picker + available slots (Mon–Fri 9–18
   in the host's timezone, 30-min, with the 4-hour minimum notice and
   60-day window applied). Picks a slot.
3. **Booker form** — same page, slide-up form. Name + email are
   required (system fields); `Company` and `What would you like to discuss?`
   are below them. Prospect fills both.
4. **Submit** — POST to `/api/book/event` (`apps/web/pages/api/book/event.ts`).
   bookings@glnkco.com creates the booking row, fires confirmation emails to host and
   prospect, and emits `BOOKING_CREATED` to every subscribed webhook
   (here: just the platform webhook).
5. **Receiver handles the webhook** — `apps/receiver/src/receiver/main.py`
   verifies the HMAC, inserts a row into `bookings`, returns 200, and
   fires the four fan-out targets (Slack post, Resend email to the agency,
   HubSpot contact + meeting, Sheets row when configured).
6. **Confirmation page** — prospect lands on `/booking/<uid>`
   (`apps/web/app/(booking-page-wrapper)/booking/[uid]/page.tsx`).
   Sees meeting details, "Add to Google Calendar / Outlook / iCal"
   buttons, reschedule and cancel links.
7. **Confirmation email arrives** — sent by bookings@glnkco.com via SMTP (mailhog
   locally; a real SMTP provider in production). Subject template +
   body in `packages/emails/src/templates/AttendeeScheduledEmail.tsx`.
   Includes calendar invite (.ics) attachment.
8. **Calendar event** appears on the host's connected calendar
   (Google / Microsoft) thanks to the calendar OAuth wired in step 3 of
   journey 2 below.

### Journey 2 — A client onboards from invite to first booking received

1. **Welcome email** — sent out of band by the agency. Contains the
   client's `/<slug>/30min` link plus a one-time temporary password
   from `glink-provision`'s output.
2. **First login** — client opens `/auth/login`
   (`apps/web/app/(use-page-wrapper)/auth/login/page.tsx`). Enters
   email + temporary password.
3. **Onboarding redirect** — `checkOnboardingRedirect()` in
   `packages/features/auth/lib/onboardingUtils.ts` decides where they
   land. Fresh client without `completedOnboarding=true` → either
   `/getting-started/<step>` or `/onboarding/getting-started`
   depending on the `onboarding-v3` feature flag.
4. **Set a real password** — `/settings/security/password`
   (`apps/web/app/(use-page-wrapper)/settings/(settings-layout)/security/password/page.tsx`).
   Replaces the temporary password from the welcome email.
5. **Connect calendar** — `/settings/my-account/calendars`
   (`apps/web/app/(use-page-wrapper)/settings/(settings-layout)/my-account/calendars/page.tsx`).
   Click "Connect" next to Google / Microsoft / Apple, complete OAuth.
   This is the single most consequential step — without it, prospects
   can book over the host's existing meetings.
6. **Confirm timezone** — `/settings/my-account/general`. Defaults to
   what provisioning set (`America/New_York` unless overridden).
7. **Confirm working hours** — `/availability/<schedule>`
   (`apps/web/app/(use-page-wrapper)/availability/[schedule]/page.tsx`).
   The "Working Hours" schedule provisioning created defaults to
   Mon–Fri 09:00–18:00 in the timezone from step 6. Drag rows to adjust.
8. **(Optional) test the booking page** — open `/<slug>/30min` in an
   incognito window. Should mirror the configured availability.
9. **First prospect books** → triggers Journey 1 above. The agency
   sees the booking land in Slack and HubSpot before the client even
   hears the calendar notification on their phone.
