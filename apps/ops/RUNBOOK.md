# Operator runbook

Operational knowledge for the people running the booking system.
Audience is engineering / ops, not clients.

## Component map

| Piece | Path | Port | Purpose |
|---|---|---|---|
| cal.diy | `cal.diy/` (vendored) | 3000 | The booking app. Self-hosted. |
| receiver | `apps/receiver/` | 8000 | FastAPI; receives cal.diy webhooks, persists, fans out |
| provisioning | `packages/provisioning` | (CLI) | Creates clients in cal.diy + writes the manifest |
| fallback | `apps/fallback/` | (static) | Outage page; built ahead of time, served when cal.diy is down |

## One-time bootstrap

After standing up cal.diy + the receiver, run this **once** per cal.diy
instance to register the single global webhook that pipes every booking
into the receiver:

```bash
export CAL_WEB_BASE=http://localhost:3000
export RECEIVER_WEBHOOK_URL=http://host.docker.internal:8000/webhook
export CAL_WEBHOOK_SECRET=<same value as apps/receiver/.env>
export CAL_ADMIN_EMAIL=<your cal.diy system-admin email>
export CAL_ADMIN_PASSWORD=<that user's password>

uv run glink-provision bootstrap-webhook
# ✓ created (or 'already exists'): platform webhook <id>
```

The platform webhook fires for **every** booking trigger across **every**
client — `WebhookRepository.getSubscribersRaw` puts platform webhooks in
the priority-1 union branch with no scope filter. So provisioning new
clients does NOT register a per-client webhook anymore; the platform
webhook covers them.

Idempotent. Safe to re-run. Won't create duplicates.

## Decisions worth knowing about

### "Send email to additional addresses" on event types — N/A in this build

The original brief (9a) called for the agency email to be set as a CC on
every event type, in addition to the receiver email, for redundancy.

**Status: not implemented. Not reachable.**

cal.diy stripped the Workflows feature, and "send email to additional
recipients" was a Workflows action — it doesn't exist as a standalone
event-type field in this build. Confirmed by source:

- `packages/trpc/server/routers/viewer/eventTypes/heavy/update.handler.ts`
  carries the explicit comment `// Workflows feature removed - always
  disallow disabling standard emails`.
- Greps across event-type schemas for `additionalEmail | notifyEmail |
  ccEmail | emails: z.array | copyEmail` return zero hits.

**Sole agency-notification path: the receiver's email integration**
(`apps/receiver/src/receiver/integrations/email.py`) — drops a Resend
email to `AGENCY_NOTIFY_EMAIL` for every handled webhook. That's the
redundancy the spec wanted; it just lives at the receiver layer instead
of the event-type layer.

If we ever want a *second* path (true redundancy), options:

1. Add a second target to the receiver's fan-out (already trivial — the
   `dispatch_external` orchestrator runs all targets concurrently).
2. Patch cal.diy to surface an `additionalEmails` field. Possible but
   would mean either reviving the Workflows package or writing a small
   custom field — both violate the "do not edit cal.diy code" rule.

### Webhook scope — global platform, not per-client

We previously registered a **per-user** webhook during each client's
provisioning. That worked but was N+1 (one webhook per client, all
pointing at the same receiver URL).

We switched to **one platform webhook** registered once via
`bootstrap-webhook` (above). Same coverage, one row in cal.diy's
`Webhook` table, simpler operation.

Pre-existing per-user webhooks for clients provisioned before the switch
(acme, beta, eta, gamma, zeta, lambda, mu, kappa) are still there. They
are **harmless**: the receiver dedupes on `(cal_booking_uid, event_type)`
via a UNIQUE constraint, so a double-delivery from per-user + platform
results in one row, not two. Fan-out fires only for the first.

To clean them up:

```bash
# Per-user webhooks have userId set; platform has userId=NULL + platform=true.
docker exec database psql -U unicorn_user -d calendso -c \
  $'DELETE FROM "Webhook" WHERE "userId" IS NOT NULL AND "subscriberUrl" = '"'"'http://host.docker.internal:8000/webhook'"'"';'
```

Optional. Skip unless you want a clean DB.

## Day-to-day

### Provision a new client

```bash
export CAL_WEB_BASE=http://localhost:3000
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.com --slug acme \
    --tz America/New_York \
    --calendly-url https://calendly.com/acme-inc/30min   # optional, fallback embed
```

Standard policy (set centrally — change in `packages/provisioning/src/provisioning/defaults.py`):

| Setting | Value |
|---|---|
| Event-type length | 30 min |
| Working hours | Mon–Fri 09:00–18:00 (client tz) |
| Buffers | 15 min before + after |
| Minimum notice | 4 hours |
| Booking window | 60 days, rolling |
| **Max bookings per day** | **5** |
| Booking questions | name, email + Company, "What would you like to discuss?" |

### Rebuild the fallback site

The fallback is a static export. Re-run after provisioning a new client
or changing a `calendly_url`:

```bash
cd apps/fallback
npm run build      # regenerates ./out
npm run serve      # serve at :3030, or upload ./out to your static host
```

It reads `../../.data/clients.json` — the manifest that provisioning
maintains automatically. Override path via `CLIENTS_MANIFEST_PATH`.

### Add fan-out targets

All four targets (Slack, HubSpot, Resend, Google Sheets) live in
`apps/receiver/src/receiver/integrations/`. Each is its own module,
each reads its own env vars, each is best-effort (a failure in one
never affects the others or the durability row).

To enable a target: drop its env vars into `apps/receiver/.env` and
`docker compose up -d --force-recreate receiver`. To disable a target:
unset its env vars. Receiver logs `fan-out integrations configured: [...]`
on startup so you can confirm.

| Target | Env it needs |
|---|---|
| Slack | `SLACK_WEBHOOK_URL` |
| HubSpot | `HUBSPOT_TOKEN` (+ optional `HUBSPOT_PIPELINE_ID`, `HUBSPOT_DEAL_STAGE`) |
| Email (Resend) | `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `AGENCY_NOTIFY_EMAIL` |
| Google Sheets | `GOOGLE_SHEETS_CREDENTIALS_JSON` (service-account JSON, single line) + `GOOGLE_SHEETS_SPREADSHEET_ID` (+ optional `GOOGLE_SHEETS_TAB_NAME`, default `Bookings`). The service account must be granted Editor access on the target spreadsheet. |

### Rotating the webhook secret

1. Generate a new secret: `openssl rand -hex 32`.
2. Update `apps/receiver/.env` `CAL_WEBHOOK_SECRET=<new>`.
3. Restart receiver: `docker compose -f apps/receiver/docker-compose.yml up -d --force-recreate receiver`.
4. Re-run `glink-provision bootstrap-webhook` — `ensure_platform_webhook` will detect the existing webhook by URL and *not* recreate it. To actually rotate the secret in cal.diy, the simplest path is to delete the platform webhook row (`DELETE FROM "Webhook" WHERE platform = true`) and re-run the bootstrap. cal.diy itself doesn't expose a "rotate secret" mutation we can call from outside.

### Resetting the local cal.diy stack

Wipes everything (cal.diy users, schedules, event types, webhooks) and
rebuilds from migrations:

```bash
cd cal.diy
docker compose down -v
docker compose up -d
# … then in glink-booking:
rm -rf .data/                            # nuke per-client records
docker compose -f apps/receiver/docker-compose.yml down -v   # nuke receiver Postgres
docker compose -f apps/receiver/docker-compose.yml up -d
uv run glink-provision bootstrap-webhook
# re-provision clients...
```

## Known limitations

- **Crash between 2xx and fan-out** — see `apps/receiver/src/receiver/fanout.py` docstring. The DB row persists; the external dispatch is lost. No retry queue today.
- **HubSpot custom utm_* properties** — must exist on the Contact object before the integration can write them. One-time setup via `POST /crm/v3/properties/contacts` for each of `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (string/text). Documented in commit message of the fan-out integration commit.
- **HubSpot rejects `*.test` TLDs** as invalid emails. Test data using `example.com` works fine; test data using `example.test` does not. Production data is unaffected.
- **Resend in dev** — using the test sender `onboarding@resend.dev` only sends to your own verified address. For production, verify a real sender domain.
